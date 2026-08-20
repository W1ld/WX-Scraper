import asyncio
import json
import random
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import config
from client_manager import TwitterClient
from parser import parse_tweet, extract_tweet_from_result
from exporter import save_checkpoint

SEARCH_TIMELINE_URL = "https://x.com/i/api/graphql/hyPfJYJ_XAtDYoslQc-Rgg/SearchTimeline"
TWEET_DETAIL_URL = "https://x.com/i/api/graphql/XMOz5h24KAZ86qKffKTLdQ/TweetDetail"

GQL_FEATURES = {
    "rweb_tipjar_consumption_enabled": True,
    "responsive_web_graphql_exclude_directive_enabled": True,
    "verified_phone_label_enabled": False,
    "creator_subscriptions_tweet_preview_api_enabled": True,
    "responsive_web_graphql_timeline_navigation_enabled": True,
    "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
    "communities_web_enable_tweet_community_results_fetch": True,
    "c9s_tweet_anatomy_moderator_badge_enabled": True,
    "articles_preview_enabled": True,
    "responsive_web_edit_tweet_api_enabled": True,
    "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
    "view_counts_everywhere_api_enabled": True,
    "longform_notetweets_consumption_enabled": True,
    "responsive_web_twitter_article_tweet_consumption_enabled": True,
    "tweet_awards_web_tipping_enabled": False,
    "creator_subscriptions_quote_tweet_preview_enabled": False,
    "freedom_of_speech_not_reach_fetch_enabled": True,
    "standardized_nudges_misinfo": True,
    "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
    "rweb_video_timestamps_enabled": True,
    "longform_notetweets_rich_text_read_enabled": True,
    "longform_notetweets_inline_media_enabled": True,
    "responsive_web_enhance_cards_enabled": False
}

def extract_cursor_from_instructions(instructions: List[dict], cursor_type: str = "Bottom") -> Optional[str]:
    """
    Extracts the bottom/top cursor token across all GraphQL instructions 
    (TimelineAddEntries, TimelineReplaceEntry, TimelineAddToModule).
    """
    target_type = cursor_type.lower()
    for inst in instructions:
        itype = inst.get("type", "")
        if itype == "TimelineAddEntries":
            for entry in inst.get("entries", []):
                eid = entry.get("entryId", "").lower()
                content = entry.get("content", {})
                ctype = str(content.get("cursorType") or content.get("itemContent", {}).get("cursorType") or "").lower()
                if target_type in eid or ctype == target_type or (target_type == "bottom" and "showmore" in eid):
                    val = (
                        content.get("value")
                        or content.get("itemContent", {}).get("value")
                        or content.get("operation", {}).get("cursor", {}).get("value")
                    )
                    if val:
                        return val

        elif itype == "TimelineReplaceEntry":
            entry = inst.get("entry", {})
            eid = (entry.get("entryId", "") or inst.get("entryIdToReplace", "") or inst.get("entry_id_to_replace", "")).lower()
            content = entry.get("content", {})
            ctype = str(content.get("cursorType") or content.get("itemContent", {}).get("cursorType") or "").lower()
            if target_type in eid or ctype == target_type or (target_type == "bottom" and "showmore" in eid):
                val = (
                    content.get("value")
                    or content.get("itemContent", {}).get("value")
                    or content.get("operation", {}).get("cursor", {}).get("value")
                )
                if val:
                    return val

    return None

async def handle_rate_limit(response_headers: dict, checkpoint_data: List[Dict[str, Any]] | None = None, prefix: str = "backup"):
    """
    Handles Twitter rate limit (HTTP 429) by waiting until the reset timestamp.
    Also automatically saves a temporary checkpoint backup to disk.
    """
    if checkpoint_data:
        saved_path = save_checkpoint(checkpoint_data, prefix=prefix)
        if saved_path:
            print(f"\n[Checkpoint] {len(checkpoint_data)} data sementara otomatis diamankan di: {saved_path}")

    reset_header = response_headers.get("x-rate-limit-reset")
    if reset_header and reset_header.isdigit():
        reset_timestamp = int(reset_header)
        wait_seconds = max(int(reset_timestamp - time.time()) + 5, 10)
    else:
        wait_seconds = 900 # default 15 minutes

    print(f"\n[!] Terkena Rate Limit (HTTP 429). Menunggu selama {wait_seconds} detik hingga kuota di-reset...")
    for remaining in range(wait_seconds, 0, -1):
        mins, secs = divmod(remaining, 60)
        print(f"\r    Cooldown rate limit: {mins:02d}:{secs:02d} tersisa ({remaining}s)...", end="", flush=True)
        await asyncio.sleep(1)
    print("\n[+] Cooldown selesai, secara otomatis melanjutkan pengambilan data...")

async def search_tweets(
    client: TwitterClient,
    query: str,
    product: str = "Top",
    max_tweets: int = 100,
    delay_range: Tuple[float, float] = (config.DELAY_MIN, config.DELAY_MAX)
) -> List[Dict[str, Any]]:
    """
    Scrapes tweets based on a search query / keyword / hashtag (Main tweets only).
    """
    print(f"\n[+] Memulai pencarian tweet...")
    print(f"    Query: '{query}' | Mode: {product} | Target: {max_tweets} tweets")

    collected_tweets: List[Dict[str, Any]] = []
    seen_ids = set()
    cursor = None
    empty_batches_count = 0
    http = client.get_http_client()

    while len(collected_tweets) < max_tweets:
        variables = {
            "rawQuery": query,
            "count": min(20, max_tweets - len(collected_tweets) + 5),
            "querySource": "typed_query",
            "product": product
        }
        if cursor:
            variables["cursor"] = cursor

        payload = {
            "variables": variables,
            "features": GQL_FEATURES,
            "queryId": "hyPfJYJ_XAtDYoslQc-Rgg"
        }

        try:
            r = await http.post(SEARCH_TIMELINE_URL, json=payload)
        except Exception as e:
            print(f"[!] Network error: {e}. Mencoba lagi dalam 5 detik...")
            await asyncio.sleep(5)
            continue

        if r.status_code == 429:
            await handle_rate_limit(dict(r.headers), checkpoint_data=collected_tweets, prefix=f"search_{query}")
            continue
        elif r.status_code != 200:
            print(f"[X] Request gagal dengan status code {r.status_code}: {r.text[:200]}")
            break

        data = r.json()
        instructions = data.get("data", {}).get("search_by_raw_query", {}).get("search_timeline", {}).get("timeline", {}).get("instructions", [])
        
        entries = []
        for inst in instructions:
            if inst.get("type") == "TimelineAddEntries":
                entries = inst.get("entries", [])
                break

        if not entries and not instructions:
            print("[-] Tidak ada tweet baru ditemukan.")
            break

        new_cursor = extract_cursor_from_instructions(instructions, cursor_type="Bottom")
        new_batch_count = 0

        for entry in entries:
            entry_id = entry.get("entryId", "")
            content = entry.get("content", {})

            # 1. Single tweet entry
            if entry_id.startswith("tweet-") or entry_id.startswith("sq-I-t-"):
                tweet_results = content.get("itemContent", {}).get("tweet_results", {}).get("result", {})
                parsed = extract_tweet_from_result(tweet_results, row_type="main_tweet")
                if parsed and parsed["tweet_id"] not in seen_ids:
                    seen_ids.add(parsed["tweet_id"])
                    collected_tweets.append(parsed)
                    new_batch_count += 1
                    if len(collected_tweets) >= max_tweets:
                        break

            # 2. Module entries (items list)
            elif "items" in content:
                for item in content.get("items", []):
                    item_content = item.get("item", {}).get("itemContent", {})
                    tweet_results = item_content.get("tweet_results", {}).get("result", {})
                    parsed = extract_tweet_from_result(tweet_results, row_type="main_tweet")
                    if parsed and parsed["tweet_id"] not in seen_ids:
                        seen_ids.add(parsed["tweet_id"])
                        collected_tweets.append(parsed)
                        new_batch_count += 1
                        if len(collected_tweets) >= max_tweets:
                            break

        print(f"[*] Terkumpul: {len(collected_tweets)}/{max_tweets} tweets (+{new_batch_count} baru)")

        # Auto save checkpoint setiap kelipatan 100 data
        if len(collected_tweets) % 100 == 0:
            save_checkpoint(collected_tweets, prefix=f"search_{query}")

        if len(collected_tweets) >= max_tweets:
            break

        # Check empty batch and cursor end conditions
        if new_batch_count == 0:
            empty_batches_count += 1
            if empty_batches_count >= 3:
                print("[-] Tidak ada tweet baru setelah 3 percobaan halaman (end of results).")
                break
        else:
            empty_batches_count = 0

        if not new_cursor or new_cursor == cursor:
            print("[-] Tidak ada halaman hasil berikutnya (end of results).")
            break

        cursor = new_cursor
        delay = random.uniform(*delay_range)
        await asyncio.sleep(delay)

    print(f"[OK] Selesai. Total {len(collected_tweets)} tweet berhasil dikumpulkan.")
    return collected_tweets

async def fetch_tweet_replies(
    client: TwitterClient,
    tweet_id: str,
    max_replies: int = 5,
    delay_range: Tuple[float, float] = (config.DELAY_MIN, config.DELAY_MAX)
) -> List[Dict[str, Any]]:
    """
    Fetches up to max_replies for a specific tweet using TweetDetail endpoint.
    """
    if max_replies <= 0:
        return []

    http = client.get_http_client()
    replies: List[Dict[str, Any]] = []
    seen_reply_ids = set()
    cursor = None

    while len(replies) < max_replies:
        variables = {
            "focalTweetId": tweet_id,
            "with_rux_injections": False,
            "includePromotedContent": False,
            "withCommunity": True,
            "withQuickPromoteEligibilityTweetFields": True,
            "withBirdwatchNotes": True,
            "withVoice": True,
            "withV2Timeline": True
        }
        if cursor:
            variables["cursor"] = cursor

        payload = {
            "variables": variables,
            "features": GQL_FEATURES,
            "queryId": "XMOz5h24KAZ86qKffKTLdQ"
        }

        try:
            r = await http.post(TWEET_DETAIL_URL, json=payload)
        except Exception:
            break

        if r.status_code == 429:
            await handle_rate_limit(dict(r.headers))
            continue
        elif r.status_code != 200:
            break

        data = r.json()
        instructions = data.get("data", {}).get("threaded_conversation_with_injections_v2", {}).get("instructions", [])
        
        entries = []
        for inst in instructions:
            if inst.get("type") == "TimelineAddEntries":
                entries = inst.get("entries", [])
                break

        if not entries and not instructions:
            break

        new_cursor = extract_cursor_from_instructions(instructions, cursor_type="Bottom")
        new_batch_count = 0

        for entry in entries:
            entry_id = entry.get("entryId", "")
            # Check reply items
            if entry_id.startswith("conversationthread-"):
                items = entry.get("content", {}).get("items", [])
                for item in items:
                    item_content = item.get("item", {}).get("itemContent", {})
                    tweet_results = item_content.get("tweet_results", {}).get("result", {})
                    parsed = extract_tweet_from_result(tweet_results, row_type="reply", parent_tweet_id=tweet_id)
                    if parsed and parsed["tweet_id"] != tweet_id and parsed["tweet_id"] not in seen_reply_ids:
                        seen_reply_ids.add(parsed["tweet_id"])
                        replies.append(parsed)
                        new_batch_count += 1
                        if len(replies) >= max_replies:
                            break

            elif (entry_id.startswith("tweet-") or entry_id.startswith("sq-I-t-")) and entry_id != f"tweet-{tweet_id}":
                tweet_results = entry.get("content", {}).get("itemContent", {}).get("tweet_results", {}).get("result", {})
                parsed = extract_tweet_from_result(tweet_results, row_type="reply", parent_tweet_id=tweet_id)
                if parsed and parsed["tweet_id"] != tweet_id and parsed["tweet_id"] not in seen_reply_ids:
                    seen_reply_ids.add(parsed["tweet_id"])
                    replies.append(parsed)
                    new_batch_count += 1
                    if len(replies) >= max_replies:
                        break

            if len(replies) >= max_replies:
                break

        # Stop if no new replies in this page or target reached
        if new_batch_count == 0 or len(replies) >= max_replies or not new_cursor or new_cursor == cursor:
            break
        cursor = new_cursor
        await asyncio.sleep(random.uniform(*delay_range))

    return replies[:max_replies]

async def search_tweets_with_replies(
    client: TwitterClient,
    query: str,
    product: str = "Top",
    max_tweets: int = 100,
    replies_per_tweet: int = 5,
    delay_range: Tuple[float, float] = (config.DELAY_MIN, config.DELAY_MAX)
) -> List[Dict[str, Any]]:
    """
    Scrapes tweets based on query AND fetches comments/replies for EACH tweet.
    Supports large datasets (1000 - 1500+ items) with auto-checkpointing and rate limit pause/resume.
    """
    print(f"\n[+] Memulai Pencarian Tweet + Ambil Komentar per Tweet...", flush=True)
    print(f"    Query: '{query}' | Mode: {product}", flush=True)
    print(f"    Target Tweet Utama: {max_tweets} post", flush=True)
    print(f"    Target Komentar: Maksimal {replies_per_tweet} komentar per tweet", flush=True)

    # Step 1: Collect main tweets from search
    main_tweets = await search_tweets(
        client=client,
        query=query,
        product=product,
        max_tweets=max_tweets,
        delay_range=delay_range
    )

    if not main_tweets:
        return []

    print(f"\n[OK] Berhasil mengumpulkan {len(main_tweets)} tweet utama.", flush=True)
    print(f"[+] Sekarang memproses komentar untuk masing-masing tweet (maks {replies_per_tweet} komentar/tweet)...\n", flush=True)

    combined_dataset: List[Dict[str, Any]] = []
    total_comments_collected = 0

    # Step 2: For each tweet, fetch replies
    for idx, main_tweet in enumerate(main_tweets, 1):
        combined_dataset.append(main_tweet)
        tweet_id = main_tweet["tweet_id"]
        author = main_tweet.get("username", "unknown")
        reported_replies = int(main_tweet.get("replies", 0) or 0)

        # Cek jika tidak membutuhkan replies atau jika tweet memang tidak memiliki komentar
        if replies_per_tweet > 0:
            if reported_replies == 0:
                print(f"  [{idx}/{len(main_tweets)}] Tweet ID {tweet_id} (@{author}): 0 komentar (dilewati).", flush=True)
            else:
                target_count = min(replies_per_tweet, reported_replies)
                print(f"  [{idx}/{len(main_tweets)}] Mengambil komentar tweet ID {tweet_id} (@{author}, ada ~{reported_replies} komentar)...", flush=True)
                tweet_replies = await fetch_tweet_replies(
                    client=client,
                    tweet_id=tweet_id,
                    max_replies=target_count,
                    delay_range=delay_range
                )
                combined_dataset.extend(tweet_replies)
                total_comments_collected += len(tweet_replies)
                print(f"       -> Berhasil mengambil {len(tweet_replies)} komentar.", flush=True)
                # Delay hanya jika benar-benar melakukan HTTP request ke server Twitter
                if idx < len(main_tweets):
                    delay = random.uniform(*delay_range)
                    await asyncio.sleep(delay)
        else:
            print(f"  [{idx}/{len(main_tweets)}] Tweet ID {tweet_id} (@{author}) dicatat.", flush=True)

        # Simpan checkpoint otomatis setiap kelipatan 50 tweet utama
        if idx % 50 == 0:
            save_checkpoint(combined_dataset, prefix=f"combo_{query}")

    print(f"\n[OK] Proses Selesai!", flush=True)
    print(f"    Total Tweet Utama: {len(main_tweets)}", flush=True)
    print(f"    Total Komentar: {total_comments_collected}", flush=True)
    print(f"    Total Baris Data: {len(combined_dataset)}", flush=True)

    return combined_dataset

def extract_tweet_id(input_str: str) -> str:
    """Extracts numeric tweet ID from either a raw ID string or a full Twitter URL."""
    match = re.search(r"status/(\d+)", input_str)
    if match:
        return match.group(1)
    digits = re.sub(r"\D", "", input_str.strip())
    return digits if digits else input_str.strip()

async def get_tweet_detail_and_replies(
    client: TwitterClient,
    tweet_id_or_url: str,
    max_replies: int = 50,
    delay_range: Tuple[float, float] = (config.DELAY_MIN, config.DELAY_MAX)
) -> Dict[str, Any]:
    """
    Scrapes a specific single Tweet detail and its comments/replies.
    """
    tweet_id = extract_tweet_id(tweet_id_or_url)
    if not tweet_id:
        print("[X] Format Tweet ID atau URL tidak valid.")
        return {"main_tweet": None, "replies": []}

    print(f"\n[+] Mengambil detail tweet ID: {tweet_id} (Target replies: maks {max_replies})...")
    http = client.get_http_client()
    
    main_tweet_data = None
    replies_data: List[Dict[str, Any]] = []
    seen_ids = set()
    cursor = None

    while True:
        variables = {
            "focalTweetId": tweet_id,
            "with_rux_injections": False,
            "includePromotedContent": False,
            "withCommunity": True,
            "withQuickPromoteEligibilityTweetFields": True,
            "withBirdwatchNotes": True,
            "withVoice": True,
            "withV2Timeline": True
        }
        if cursor:
            variables["cursor"] = cursor

        payload = {
            "variables": variables,
            "features": GQL_FEATURES,
            "queryId": "XMOz5h24KAZ86qKffKTLdQ"
        }

        try:
            r = await http.post(TWEET_DETAIL_URL, json=payload)
        except Exception as e:
            print(f"[X] Gagal melakukan request detail tweet: {e}")
            break

        if r.status_code == 429:
            await handle_rate_limit(dict(r.headers))
            continue

        if r.status_code != 200:
            print(f"[X] Gagal mengambil detail tweet (Status {r.status_code}).")
            break

        data = r.json()
        instructions = data.get("data", {}).get("threaded_conversation_with_injections_v2", {}).get("instructions", [])
        
        entries = []
        for inst in instructions:
            if inst.get("type") == "TimelineAddEntries":
                entries = inst.get("entries", [])
                break

        if not entries and not instructions:
            break

        new_cursor = extract_cursor_from_instructions(instructions, cursor_type="Bottom")
        new_batch_count = 0

        for entry in entries:
            entry_id = entry.get("entryId", "")
            if entry_id == f"tweet-{tweet_id}" and not main_tweet_data:
                tweet_results = entry.get("content", {}).get("itemContent", {}).get("tweet_results", {}).get("result", {})
                main_tweet_data = extract_tweet_from_result(tweet_results, row_type="main_tweet")
                
            elif entry_id.startswith("conversationthread-"):
                items = entry.get("content", {}).get("items", [])
                for item in items:
                    item_content = item.get("item", {}).get("itemContent", {})
                    tweet_results = item_content.get("tweet_results", {}).get("result", {})
                    parsed = extract_tweet_from_result(tweet_results, row_type="reply", parent_tweet_id=tweet_id)
                    if parsed and parsed["tweet_id"] != tweet_id and parsed["tweet_id"] not in seen_ids:
                        seen_ids.add(parsed["tweet_id"])
                        replies_data.append(parsed)
                        new_batch_count += 1
                        if len(replies_data) >= max_replies:
                            break

            elif (entry_id.startswith("tweet-") or entry_id.startswith("sq-I-t-")) and entry_id != f"tweet-{tweet_id}":
                tweet_results = entry.get("content", {}).get("itemContent", {}).get("tweet_results", {}).get("result", {})
                parsed = extract_tweet_from_result(tweet_results, row_type="reply", parent_tweet_id=tweet_id)
                if parsed and parsed["tweet_id"] != tweet_id and parsed["tweet_id"] not in seen_ids:
                    seen_ids.add(parsed["tweet_id"])
                    replies_data.append(parsed)
                    new_batch_count += 1
                    if len(replies_data) >= max_replies:
                        break

            if len(replies_data) >= max_replies:
                break

        if len(replies_data) >= max_replies or not new_cursor or new_cursor == cursor or max_replies == 0:
            break
            
        cursor = new_cursor
        await asyncio.sleep(random.uniform(*delay_range))

    # Pastikan data terpotong persis sesuai kuota max_replies
    replies_data = replies_data[:max_replies]

    if main_tweet_data:
        print(f"[OK] Tweet utama ditemukan dari @{main_tweet_data['username']}")
    print(f"[OK] Ditemukan {len(replies_data)} replies (dibatasi maks {max_replies}).")

    return {
        "main_tweet": main_tweet_data,
        "replies": replies_data
    }
