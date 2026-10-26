import asyncio
import json
import random
import re
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import httpx
import config
from client_manager import InstagramClient, IG_APP_ID
from parser import parse_user_profile, parse_post_item, parse_comment_item, parse_follower_item
from exporter import save_checkpoint

# Karakter Base64 URL untuk konversi shortcode <-> media_id Instagram
IG_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"

def shortcode_to_media_id(shortcode: str) -> int:
    """Mengonversi shortcode postingan Instagram (misal: 'DBabc123') menjadi ID angka media_id."""
    media_id = 0
    for char in shortcode:
        if char not in IG_ALPHABET:
            continue
        media_id = media_id * 64 + IG_ALPHABET.index(char)
    return media_id

def media_id_to_shortcode(media_id: int) -> str:
    """Mengonversi ID angka media_id Instagram menjadi shortcode URL."""
    shortcode = ""
    while media_id > 0:
        media_id, rem = divmod(media_id, 64)
        shortcode = IG_ALPHABET[rem] + shortcode
    return shortcode

def extract_shortcode(url_or_code: str) -> str:
    """Mengekstrak shortcode bersih dari URL postingan atau teks kode yang diinput user."""
    cleaned = url_or_code.strip()
    match = re.search(r"instagram\.com/(?:p|reel|tv)/([A-Za-z0-9_-]+)", cleaned)
    if match:
        return match.group(1)
    
    # Jika pengguna hanya memasukkan shortcode mentah
    cleaned = cleaned.strip("/ ")
    if "/" not in cleaned and len(cleaned) >= 3:
        return cleaned
        
    return cleaned

async def human_delay():
    """Memberikan jeda acak antar request untuk mensimulasikan perilaku manusia asli."""
    delay = random.uniform(config.DELAY_MIN, config.DELAY_MAX)
    await asyncio.sleep(delay)

async def handle_rate_limit(wait_seconds: int = 60, checkpoint_data: Optional[List[dict]] = None, prefix: str = "checkpoint"):
    """Menangani pembatasan kuota (HTTP 429) dengan countdown waktu tunggu dan auto-checkpoint."""
    if checkpoint_data:
        saved = save_checkpoint(checkpoint_data, prefix=prefix)
        if saved:
            print(f"\n[Checkpoint] {len(checkpoint_data)} data diamankan di: {saved}")

    print(f"\n[!] Terkena Rate Limit Instagram (HTTP 429). Istirahat selama {wait_seconds} detik...")
    for remaining in range(wait_seconds, 0, -1):
        mins, secs = divmod(remaining, 60)
        print(f"\r    Cooldown: {mins:02d}:{secs:02d} tersisa ({remaining}s)...", end="", flush=True)
        await asyncio.sleep(1)
    print("\n[+] Cooldown selesai, melanjutkan request...\n")

# ==============================================================================
# 1. SCRAPE USER PROFILE & POSTS (DENGAN OPSIONAL DRILL-DOWN KOMENTAR)
# ==============================================================================

async def get_user_profile(client: InstagramClient, username: str) -> Tuple[Optional[dict], Optional[dict]]:
    """
    Mengambil data profil Instagram & objek pengguna awal dari web_profile_info.
    Returns: (profile_metadata, raw_user_dict)
    """
    clean_user = username.strip().lstrip("@")
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={clean_user}"
    http = client.get_http_client()

    headers = {
        'referer': f'https://www.instagram.com/{clean_user}/'
    }

    try:
        r = await http.get(url, headers=headers)
        if r.status_code == 200:
            data = r.json().get("data", {})
            user_data = data.get("user")
            if user_data:
                profile_meta = parse_user_profile(user_data)
                return profile_meta, user_data
        elif r.status_code == 404:
            print(f"[!] Akun @{clean_user} tidak ditemukan.")
            return None, None
        elif r.status_code == 429:
            await handle_rate_limit(60)
            return await get_user_profile(client, clean_user)
        elif "checkpoint_required" in r.text:
            print("\n[!] Akun terkena checkpoint verifikasi Instagram. Buka browser instagram.com untuk verifikasi.")
            return None, None
        else:
            print(f"[!] Gagal mengambil profil @{clean_user}: HTTP {r.status_code}")
    except Exception as e:
        print(f"[!] Error saat request profil: {e}")

    return None, None

async def scrape_profile_posts(
    client: InstagramClient,
    username: str,
    limit: int = 50,
    fetch_comments: bool = False,
    max_comments_per_post: int = 20,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> List[Dict[str, Any]]:
    """
    Mengambil daftar postingan dari akun Instagram (Feed & Reels).
    Dilengkapi fitur drill-down 2-in-1 untuk menarik komentar pada masing-masing post.
    """
    clean_user = username.strip().lstrip("@")
    profile_meta, raw_user = await get_user_profile(client, clean_user)
    if not raw_user:
        return []

    user_id = str(raw_user.get("id", ""))
    is_private = raw_user.get("is_private", False)

    if is_private and not raw_user.get("followed_by_viewer", True):
        print(f"[!] Akun @{clean_user} bersifat Privat dan sesi Anda belum mem-follow akun ini.")
        return []

    collected_data: List[Dict[str, Any]] = []
    seen_ids = set()

    # Halaman 1 dari web_profile_info
    timeline = raw_user.get("edge_owner_to_timeline_media", {})
    edges = timeline.get("edges", [])
    page_info = timeline.get("page_info", {})
    has_next_page = page_info.get("has_next_page", False)
    end_cursor = page_info.get("end_cursor", "")

    total_posts_available = timeline.get("count", 0)
    print(f"\n[+] Memulai penarikan {min(limit, total_posts_available)} postingan dari @{clean_user}...")

    # Parsing postingan halaman 1
    for edge in edges:
        node = edge.get("node", {})
        post_item = parse_post_item(node, owner_info=profile_meta)
        if post_item and post_item["post_id"] not in seen_ids:
            seen_ids.add(post_item["post_id"])
            collected_data.append(post_item)

            if progress_callback:
                progress_callback(len(collected_data), limit, f"Post: {post_item['shortcode']}")

            # Drill-down komentar jika diaktifkan
            if fetch_comments and post_item["comments_count"] > 0:
                print(f"    -> Menggali hingga {max_comments_per_post} komentar dari post {post_item['shortcode']}...")
                comments = await scrape_post_comments(
                    client,
                    post_input=post_item["shortcode"],
                    limit=max_comments_per_post,
                    parent_post_id=post_item["post_id"],
                    show_log=False
                )
                collected_data.extend(comments)

            if len(seen_ids) >= limit:
                break

    # Paginasi halaman selanjutnya jika limit belum tercapai
    http = client.get_http_client()
    query_hash = "69cba40317214236af40e7efa697781d" # Web timeline GraphQL query hash

    while has_next_page and end_cursor and len(seen_ids) < limit:
        await human_delay()

        # Coba via GraphQL Web Query
        gql_url = "https://www.instagram.com/graphql/query/"
        variables = json.dumps({"id": user_id, "first": 12, "after": end_cursor})
        params = {
            "query_hash": query_hash,
            "variables": variables
        }
        headers = {'referer': f'https://www.instagram.com/{clean_user}/'}

        try:
            r = await http.get(gql_url, params=params, headers=headers)
            
            if r.status_code == 200:
                res_data = r.json().get("data", {})
                user_node = res_data.get("user", {})
                tl_media = user_node.get("edge_owner_to_timeline_media", {})
                new_edges = tl_media.get("edges", [])
                p_info = tl_media.get("page_info", {})
                has_next_page = p_info.get("has_next_page", False)
                end_cursor = p_info.get("end_cursor", "")

                if not new_edges:
                    break

                for edge in new_edges:
                    node = edge.get("node", {})
                    post_item = parse_post_item(node, owner_info=profile_meta)
                    if post_item and post_item["post_id"] not in seen_ids:
                        seen_ids.add(post_item["post_id"])
                        collected_data.append(post_item)

                        if progress_callback:
                            progress_callback(len(collected_data), limit, f"Post: {post_item['shortcode']}")

                        if fetch_comments and post_item["comments_count"] > 0:
                            comments = await scrape_post_comments(
                                client,
                                post_input=post_item["shortcode"],
                                limit=max_comments_per_post,
                                parent_post_id=post_item["post_id"],
                                show_log=False
                            )
                            collected_data.extend(comments)

                        if len(seen_ids) >= limit:
                            break

                # Auto-checkpoint setiap kelipatan 25 item
                if len(seen_ids) % 25 == 0:
                    save_checkpoint(collected_data, prefix=f"profile_{clean_user}")

            elif r.status_code == 429:
                await handle_rate_limit(60, checkpoint_data=collected_data, prefix=f"profile_{clean_user}")
                continue
            elif "checkpoint_required" in r.text:
                print("\n[!] Checkpoint verifikasi Instagram terpicu. Menyimpan data sementara...")
                save_checkpoint(collected_data, prefix=f"profile_{clean_user}")
                break
            else:
                # Fallback ke REST API v1 jika GraphQL gagal
                rest_url = f"https://www.instagram.com/api/v1/feed/user/{user_id}/"
                rest_params = {"count": 12, "max_id": end_cursor}
                r_rest = await http.get(rest_url, params=rest_params, headers=headers)
                if r_rest.status_code == 200:
                    rest_data = r_rest.json()
                    items = rest_data.get("items", [])
                    has_next_page = rest_data.get("more_available", False)
                    end_cursor = rest_data.get("next_max_id", "")
                    
                    for item in items:
                        post_item = parse_post_item(item, owner_info=profile_meta)
                        if post_item and post_item["post_id"] not in seen_ids:
                            seen_ids.add(post_item["post_id"])
                            collected_data.append(post_item)
                            if len(seen_ids) >= limit:
                                break
                else:
                    print(f"[!] Gagal mengambil pagination post: HTTP {r.status_code}")
                    break

        except Exception as e:
            print(f"[!] Error saat paginasi post: {e}")
            break

    return collected_data

# ==============================================================================
# 2. SCRAPE KOMENTAR DARI POSTINGAN (URL / SHORTCODE)
# ==============================================================================

async def scrape_post_comments(
    client: InstagramClient,
    post_input: str,
    limit: int = 100,
    parent_post_id: Optional[str] = None,
    show_log: bool = True,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> List[Dict[str, Any]]:
    """
    Mengambil komentar dan balasan (threaded replies) dari sebuah postingan Instagram.
    Mendukung input URL postingan (p/reel/tv) maupun shortcode.
    """
    shortcode = extract_shortcode(post_input)
    if not shortcode:
        print(f"[!] Shortcode atau URL tidak valid: {post_input}")
        return []

    media_id = parent_post_id or str(shortcode_to_media_id(shortcode))
    http = client.get_http_client()

    collected_comments: List[Dict[str, Any]] = []
    seen_comment_ids = set()
    cursor: Optional[str] = None
    has_more = True

    if show_log:
        print(f"\n[+] Mengambil komentar dari post '{shortcode}' (Media ID: {media_id})...")

    headers = {
        'referer': f'https://www.instagram.com/p/{shortcode}/'
    }

    while has_more and len(collected_comments) < limit:
        url = f"https://www.instagram.com/api/v1/comments/{media_id}/parent/?can_support_threading=true&permalink_enabled=false"
        params = {}
        if cursor:
            params["min_id"] = cursor

        try:
            r = await http.get(url, params=params, headers=headers)
            
            if r.status_code == 200:
                data = r.json()
                comments_list = data.get("comments", [])
                has_more = data.get("has_more_comments", False)
                cursor = data.get("next_min_id")

                if not comments_list:
                    break

                for comment in comments_list:
                    c_item = parse_comment_item(
                        comment=comment,
                        shortcode=shortcode,
                        post_id=media_id,
                        row_type="comment"
                    )
                    if c_item and c_item["comment_id"] not in seen_comment_ids:
                        seen_comment_ids.add(c_item["comment_id"])
                        collected_comments.append(c_item)

                        if progress_callback:
                            progress_callback(len(collected_comments), limit, f"Komentar oleh @{c_item['comment_author_username']}")

                        # Ambil child replies jika ada
                        child_comments = comment.get("child_comments", [])
                        for child in child_comments:
                            child_item = parse_comment_item(
                                comment=child,
                                shortcode=shortcode,
                                post_id=media_id,
                                row_type="reply",
                                parent_comment_id=c_item["comment_id"]
                            )
                            if child_item and child_item["comment_id"] not in seen_comment_ids:
                                seen_comment_ids.add(child_item["comment_id"])
                                collected_comments.append(child_item)

                        if len(collected_comments) >= limit:
                            break

                # Jeda antar halaman komentar
                if has_more and cursor and len(collected_comments) < limit:
                    await human_delay()

            elif r.status_code == 429:
                await handle_rate_limit(60, checkpoint_data=collected_comments, prefix=f"comments_{shortcode}")
                continue
            elif "checkpoint_required" in r.text:
                print("\n[!] Checkpoint verifikasi Instagram terpicu saat membaca komentar.")
                save_checkpoint(collected_comments, prefix=f"comments_{shortcode}")
                break
            else:
                if show_log:
                    print(f"[!] Gagal mengambil komentar: HTTP {r.status_code}")
                break

        except Exception as e:
            if show_log:
                print(f"[!] Error saat mengambil komentar: {e}")
            break

    return collected_comments

async def scrape_multiple_posts_comments(
    client: InstagramClient,
    post_inputs: List[str],
    limit_per_post: int = 50
) -> List[Dict[str, Any]]:
    """
    Mengambil komentar dari beberapa link postingan Instagram secara berurutan.
    """
    all_comments: List[Dict[str, Any]] = []
    print(f"\n[+] Memproses {len(post_inputs)} postingan untuk penarikan komentar...")

    for i, post_input in enumerate(post_inputs, 1):
        print(f"\n[{i}/{len(post_inputs)}] Memproses post: {post_input}")
        comments = await scrape_post_comments(
            client=client,
            post_input=post_input,
            limit=limit_per_post,
            show_log=True
        )
        all_comments.extend(comments)
        print(f"[✓] Didapat {len(comments)} komentar dari post ini (Total: {len(all_comments)})")

        if i < len(post_inputs):
            await human_delay()

    return all_comments

# ==============================================================================
# 3. SCRAPE POSTINGAN BERDASARKAN HASHTAG (#HASHTAG)
# ==============================================================================

async def scrape_hashtag_posts(
    client: InstagramClient,
    hashtag: str,
    limit: int = 50,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> List[Dict[str, Any]]:
    """
    Mengambil postingan publik berdasarkan #hashtag tertentu.
    """
    clean_tag = hashtag.strip().lstrip("#")
    http = client.get_http_client()

    url = f"https://www.instagram.com/api/v1/tags/web_info/?tag_name={clean_tag}"
    headers = {
        'referer': f'https://www.instagram.com/explore/tags/{clean_tag}/'
    }

    collected_data: List[Dict[str, Any]] = []
    seen_ids = set()

    print(f"\n[+] Mencari postingan untuk tag #{clean_tag}...")

    try:
        r = await http.get(url, headers=headers)
        if r.status_code == 200:
            data = r.json().get("data", {})
            total_count = data.get("count", 0)
            print(f"[+] Total postingan terindeks #{clean_tag}: {total_count:,}")

            # Top & Recent sections
            sections = []
            if "top" in data and "sections" in data["top"]:
                sections.extend(data["top"]["sections"])
            if "recent" in data and "sections" in data["recent"]:
                sections.extend(data["recent"]["sections"])

            for sec in sections:
                layout_content = sec.get("layout_content", {})
                medias = layout_content.get("medias", []) or layout_content.get("fill_items", [])
                for media_wrap in medias:
                    item = media_wrap.get("media", {})
                    post_item = parse_post_item(item)
                    if post_item and post_item["post_id"] not in seen_ids:
                        seen_ids.add(post_item["post_id"])
                        collected_data.append(post_item)

                        if progress_callback:
                            progress_callback(len(collected_data), limit, f"Post: {post_item['shortcode']}")

                        if len(collected_data) >= limit:
                            break
                if len(collected_data) >= limit:
                    break

        elif r.status_code == 429:
            await handle_rate_limit(60)
            return await scrape_hashtag_posts(client, clean_tag, limit, progress_callback)
        elif "checkpoint_required" in r.text:
            print("\n[!] Checkpoint verifikasi Instagram terpicu saat pencarian hashtag.")
        else:
            print(f"[!] Gagal mengambil data hashtag #{clean_tag}: HTTP {r.status_code}")

    except Exception as e:
        print(f"[!] Error saat scraping hashtag: {e}")

    return collected_data

# ==============================================================================
# 4. RESOLVE USERNAME KE USER_ID & SCRAPE FOLLOWERS / FOLLOWING
# ==============================================================================

def extract_username(url_or_user: str) -> str:
    """Mengekstrak username bersih dari teks input, handle @, atau URL profil Instagram."""
    cleaned = url_or_user.strip()
    match = re.search(r"instagram\.com/([A-Za-z0-9_.-]+)", cleaned)
    if match:
        candidate = match.group(1).split("/")[0].split("?")[0]
        if candidate.lower() not in ("p", "reel", "tv", "stories", "explore"):
            return candidate
    return cleaned.lstrip("@").strip("/ ")

async def resolve_user_id(client: InstagramClient, username_or_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Mengonversi username, URL profil, atau user ID Instagram menjadi tuple (numeric_user_id, username_bersih).
    """
    cleaned = extract_username(username_or_id)
    if not cleaned:
        return None, None

    # Jika input sudah berupa ID angka langsung
    if cleaned.isdigit():
        return cleaned, cleaned

    http = client.get_http_client()
    url = f"https://www.instagram.com/{cleaned}/"
    headers = {
        'referer': 'https://www.instagram.com/',
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
    }

    try:
        r = await http.get(url, headers=headers)
        if r.status_code == 200:
            html = r.text
            # Ekstraksi jumlah followers/following untuk ringkasan info profil jika tersedia
            desc_m = re.search(r'<meta\s+(?:property="og:description"|name="description")\s+content="([^"]+)"', html)
            if desc_m:
                desc = desc_m.group(1)
                fol_m = re.search(r'([\d,.]+[KMkm]?)\s+Followers', desc, re.I)
                ing_m = re.search(r'([\d,.]+[KMkm]?)\s+Following', desc, re.I)
                posts_m = re.search(r'([\d,.]+[KMkm]?)\s+Posts', desc, re.I)
                parts = []
                if fol_m: parts.append(f"{fol_m.group(1)} Followers")
                if ing_m: parts.append(f"{ing_m.group(1)} Following")
                if posts_m: parts.append(f"{posts_m.group(1)} Posts")
                if parts:
                    print(f"[*] Info Profil @{cleaned}: {', '.join(parts)}")

            # Ekstraksi ID dari embedded props / profile_id / page_id
            m = re.search(r'"props":\s*\{\s*"id":\s*"(\d+)"', html)
            if m:
                return m.group(1), cleaned

            m = re.search(r'"profile_id":\s*"(\d+)"', html)
            if m:
                return m.group(1), cleaned

            m = re.search(r'"page_id":\s*"profilePage_(\d+)"', html)
            if m:
                return m.group(1), cleaned

            m = re.search(r'"container_id":\s*"(\d+)"', html)
            if m:
                return m.group(1), cleaned
        elif r.status_code == 404:
            print(f"[!] Akun @{cleaned} tidak ditemukan.")
            return None, cleaned
        else:
            print(f"[!] Respon profil @{cleaned}: HTTP {r.status_code}")
    except Exception as e:
        print(f"[!] Error saat pencarian ID @{cleaned}: {e}")

    return None, cleaned

async def scrape_profile_followers(
    client: InstagramClient,
    target: str,
    limit: int = 50,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> List[Dict[str, Any]]:
    """
    Mengambil daftar pengikut (followers) dari sebuah akun Instagram publik.
    Mendukung input username (@username), link profil, maupun user ID langsung.
    """
    user_id, username = await resolve_user_id(client, target)
    if not user_id:
        print(f"[!] Gagal menentukan ID pengguna untuk: {target}")
        return []

    http = client.get_http_client()
    collected_followers: List[Dict[str, Any]] = []
    seen_ids = set()
    cursor: Optional[str] = None
    has_more = True
    raw_count = 0
    duplicate_count = 0

    print(f"\n[+] Memulai penarikan pengikut @{username} (User ID: {user_id}, Target: {limit})...")

    headers = {
        'referer': f'https://www.instagram.com/{username}/'
    }

    while has_more and len(collected_followers) < limit:
        count = min(50, limit - len(collected_followers))
        url = f"https://www.instagram.com/api/v1/friendships/{user_id}/followers/?count={count}&search_surface=follow_list_page"
        if cursor:
            url += f"&max_id={cursor}"

        try:
            r = await http.get(url, headers=headers)
            if r.status_code == 200:
                data = r.json()
                users = data.get("users", [])
                cursor = data.get("next_max_id")
                has_more = bool(cursor and users)

                if not users:
                    break

                for u in users:
                    raw_count += 1
                    item = parse_follower_item(
                        user=u,
                        target_username=username,
                        target_user_id=user_id,
                        relationship_type="follower"
                    )
                    if item and item["user_id"] not in seen_ids:
                        seen_ids.add(item["user_id"])
                        collected_followers.append(item)

                        if progress_callback:
                            progress_callback(len(collected_followers), limit, f"Follower: @{item['username']}")

                        if len(collected_followers) >= limit:
                            break
                    else:
                        duplicate_count += 1

                # Auto-checkpoint setiap 50 follower tersimpan
                if len(collected_followers) % 50 == 0:
                    save_checkpoint(collected_followers, prefix=f"followers_{username}")

                if has_more and len(collected_followers) < limit:
                    await human_delay()

            elif r.status_code == 429:
                await handle_rate_limit(60, checkpoint_data=collected_followers, prefix=f"followers_{username}")
                continue
            elif "checkpoint_required" in r.text:
                print("\n[!] Checkpoint verifikasi Instagram terpicu saat membaca followers.")
                save_checkpoint(collected_followers, prefix=f"followers_{username}")
                break
            else:
                print(f"[!] Gagal mengambil followers: HTTP {r.status_code}")
                break

        except Exception as e:
            print(f"[!] Error saat mengambil followers: {e}")
            break

    if duplicate_count > 0:
        print(f"[i] Info: Instagram mengembalikan total {raw_count} entri data ({duplicate_count} di antaranya merupakan duplikasi cursor pagination Instagram yang disaring). Total follower unik tersimpan: {len(collected_followers)}.")

    return collected_followers

async def scrape_profile_following(
    client: InstagramClient,
    target: str,
    limit: int = 50,
    progress_callback: Optional[Callable[[int, int, str], None]] = None
) -> List[Dict[str, Any]]:
    """
    Mengambil daftar akun yang diikuti (following) oleh target profil Instagram.
    """
    user_id, username = await resolve_user_id(client, target)
    if not user_id:
        print(f"[!] Gagal menentukan ID pengguna untuk: {target}")
        return []

    http = client.get_http_client()
    collected_following: List[Dict[str, Any]] = []
    seen_ids = set()
    cursor: Optional[str] = None
    has_more = True
    raw_count = 0
    duplicate_count = 0

    print(f"\n[+] Memulai penarikan following @{username} (User ID: {user_id}, Target: {limit})...")

    headers = {
        'referer': f'https://www.instagram.com/{username}/'
    }

    while has_more and len(collected_following) < limit:
        count = min(50, limit - len(collected_following))
        url = f"https://www.instagram.com/api/v1/friendships/{user_id}/following/?count={count}"
        if cursor:
            url += f"&max_id={cursor}"

        try:
            r = await http.get(url, headers=headers)
            if r.status_code == 200:
                data = r.json()
                users = data.get("users", [])
                cursor = data.get("next_max_id")
                has_more = bool(cursor and users)

                if not users:
                    break

                for u in users:
                    raw_count += 1
                    item = parse_follower_item(
                        user=u,
                        target_username=username,
                        target_user_id=user_id,
                        relationship_type="following"
                    )
                    if item and item["user_id"] not in seen_ids:
                        seen_ids.add(item["user_id"])
                        collected_following.append(item)

                        if progress_callback:
                            progress_callback(len(collected_following), limit, f"Following: @{item['username']}")

                        if len(collected_following) >= limit:
                            break
                    else:
                        duplicate_count += 1

                if len(collected_following) % 50 == 0:
                    save_checkpoint(collected_following, prefix=f"following_{username}")

                if has_more and len(collected_following) < limit:
                    await human_delay()

            elif r.status_code == 429:
                await handle_rate_limit(60, checkpoint_data=collected_following, prefix=f"following_{username}")
                continue
            elif "checkpoint_required" in r.text:
                print("\n[!] Checkpoint verifikasi Instagram terpicu saat membaca following.")
                save_checkpoint(collected_following, prefix=f"following_{username}")
                break
            else:
                print(f"[!] Gagal mengambil following: HTTP {r.status_code}")
                break

        except Exception as e:
            print(f"[!] Error saat mengambil following: {e}")
            break

    if duplicate_count > 0:
        print(f"[i] Info: Instagram mengembalikan total {raw_count} entri data ({duplicate_count} di antaranya merupakan duplikasi cursor pagination Instagram yang disaring). Total following unik tersimpan: {len(collected_following)}.")

    return collected_following

