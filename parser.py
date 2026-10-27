from datetime import datetime, timezone
import re
from typing import Any, Dict, List, Optional

def timestamp_to_iso(ts: Optional[int | float]) -> str:
    """Mengonversi unix timestamp ke format tanggal ISO yang mudah dibaca."""
    if not ts:
        return ""
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    except Exception:
        return str(ts)

def parse_user_profile(user_dict: dict) -> Dict[str, Any]:
    """Mengekstrak metadata profil Instagram dari respon web_profile_info."""
    if not user_dict:
        return {}
    
    return {
        "user_id": str(user_dict.get("id", "")),
        "username": user_dict.get("username", ""),
        "full_name": user_dict.get("full_name", ""),
        "biography": user_dict.get("biography", ""),
        "external_url": user_dict.get("external_url", "") or "",
        "followers_count": user_dict.get("edge_followed_by", {}).get("count", 0),
        "following_count": user_dict.get("edge_follow", {}).get("count", 0),
        "posts_count": user_dict.get("edge_owner_to_timeline_media", {}).get("count", 0),
        "is_private": user_dict.get("is_private", False),
        "is_verified": user_dict.get("is_verified", False),
        "profile_pic_url": user_dict.get("profile_pic_url_hd") or user_dict.get("profile_pic_url", "")
    }

def parse_post_item(item: dict, owner_info: Optional[dict] = None) -> Optional[Dict[str, Any]]:
    """
    Menormalisasi data postingan Instagram (baik format GraphQL Node maupun REST Media Item)
    menjadi dictionary seragam yang siap diekspor ke CSV & JSON.
    """
    if not item:
        return None

    # Handle GraphQL Node structure
    if "node" in item:
        item = item["node"]

    # 1. Post IDs & URLs
    post_id = str(item.get("id") or item.get("pk", ""))
    shortcode = item.get("shortcode") or item.get("code", "")
    if not post_id and not shortcode:
        return None

    post_url = f"https://www.instagram.com/p/{shortcode}/" if shortcode else ""

    # 2. Type & Media
    typename = item.get("__typename", "")
    is_video = bool(item.get("is_video", False) or item.get("media_type") == 2)
    
    if typename:
        post_type = typename.replace("Graph", "").lower()
    else:
        mtype = item.get("media_type")
        if mtype == 1:
            post_type = "image"
        elif mtype == 2:
            post_type = "video"
        elif mtype == 8:
            post_type = "carousel"
        else:
            post_type = "post"

    display_url = item.get("display_url", "")
    if not display_url:
        candidates = item.get("image_versions2", {}).get("candidates", [])
        if candidates:
            display_url = candidates[0].get("url", "")

    video_url = item.get("video_url", "")
    if not video_url and is_video:
        vids = item.get("video_versions", [])
        if vids:
            video_url = vids[0].get("url", "")

    # Carousel media URLs
    carousel_urls = []
    children = item.get("edge_sidecar_to_children", {}).get("edges", [])
    for child in children:
        c_node = child.get("node", {})
        c_url = c_node.get("display_url") or c_node.get("video_url")
        if c_url:
            carousel_urls.append(c_url)
    if not carousel_urls and "carousel_media" in item:
        for c in item.get("carousel_media", []):
            c_cands = c.get("image_versions2", {}).get("candidates", [])
            if c_cands:
                carousel_urls.append(c_cands[0].get("url", ""))

    # 3. Caption
    caption_text = ""
    captions_edge = item.get("edge_media_to_caption", {}).get("edges", [])
    if captions_edge:
        caption_text = captions_edge[0].get("node", {}).get("text", "")
    elif isinstance(item.get("caption"), dict):
        caption_text = item.get("caption", {}).get("text", "")
    elif isinstance(item.get("caption"), str):
        caption_text = item.get("caption", "")

    # Extract Hashtags & Mentions
    hashtags = re.findall(r"#(\w+)", caption_text) if caption_text else []
    tagged_users = re.findall(r"@(\w+)", caption_text) if caption_text else []

    # 4. Metrics
    likes_count = (
        item.get("edge_media_preview_like", {}).get("count") or
        item.get("edge_liked_by", {}).get("count") or
        item.get("like_count", 0) or 0
    )
    comments_count = (
        item.get("edge_media_to_comment", {}).get("count") or
        item.get("edge_media_preview_comment", {}).get("count") or
        item.get("comment_count", 0) or 0
    )
    views_count = (
        item.get("video_view_count") or
        item.get("view_count") or
        item.get("play_count", 0) or 0
    )

    # 5. Timestamp
    raw_timestamp = item.get("taken_at_timestamp") or item.get("taken_at")
    created_at = timestamp_to_iso(raw_timestamp)

    # 6. Owner information
    owner = item.get("owner", {}) or item.get("user", {}) or {}
    owner_id = str(owner.get("id") or owner.get("pk", ""))
    owner_username = owner.get("username", "")
    owner_full_name = owner.get("full_name", "")

    if owner_info:
        if not owner_username:
            owner_username = owner_info.get("username", "")
        if not owner_full_name:
            owner_full_name = owner_info.get("full_name", "")
        if not owner_id:
            owner_id = owner_info.get("user_id", "")

    # Location
    location_data = item.get("location") or {}
    location_name = location_data.get("name", "") if isinstance(location_data, dict) else ""

    return {
        "row_type": "post",
        "post_id": post_id,
        "shortcode": shortcode,
        "post_url": post_url,
        "post_type": post_type,
        "caption": caption_text,
        "created_at": created_at,
        "timestamp": raw_timestamp or 0,
        "likes_count": likes_count,
        "comments_count": comments_count,
        "views_count": views_count,
        "is_video": is_video,
        "display_url": display_url,
        "video_url": video_url,
        "carousel_media_urls": "; ".join(carousel_urls) if carousel_urls else "",
        "hashtags": ", ".join(hashtags) if hashtags else "",
        "tagged_users": ", ".join(tagged_users) if tagged_users else "",
        "location": location_name,
        "owner_username": owner_username,
        "owner_full_name": owner_full_name,
        "owner_id": owner_id,
        # Kolom relasional untuk keseragaman jika digabung dengan komentar
        "parent_post_id": "",
        "parent_comment_id": "",
        "comment_id": "",
        "comment_text": "",
        "comment_author_username": "",
        "comment_author_name": ""
    }

def parse_comment_item(
    comment: dict,
    shortcode: str,
    post_id: str = "",
    row_type: str = "comment",
    parent_comment_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """
    Menormalisasi satu komentar atau balasan komentar Instagram.
    """
    if not comment:
        return None

    comment_id = str(comment.get("pk") or comment.get("id", ""))
    if not comment_id:
        return None

    text = comment.get("text", "")
    raw_timestamp = comment.get("created_at") or comment.get("created_at_utc")
    created_at = timestamp_to_iso(raw_timestamp)

    likes_count = comment.get("comment_like_count", 0) or comment.get("like_count", 0) or 0
    child_count = comment.get("child_comment_count", 0) or 0

    user = comment.get("user", {}) or {}
    author_username = user.get("username", "")
    author_full_name = user.get("full_name", "")
    author_id = str(user.get("pk") or user.get("id", ""))
    author_profile_pic = user.get("profile_pic_url", "")
    author_is_verified = bool(user.get("is_verified", False))

    post_url = f"https://www.instagram.com/p/{shortcode}/" if shortcode else ""

    return {
        "row_type": row_type,
        "post_id": post_id,
        "shortcode": shortcode,
        "post_url": post_url,
        "post_type": "comment",
        "caption": "",
        "created_at": created_at,
        "timestamp": raw_timestamp or 0,
        "likes_count": likes_count,
        "comments_count": child_count,
        "views_count": 0,
        "is_video": False,
        "display_url": "",
        "video_url": "",
        "carousel_media_urls": "",
        "hashtags": "",
        "tagged_users": "",
        "location": "",
        "owner_username": "",
        "owner_full_name": "",
        "owner_id": "",
        # Kolom relasi komentar
        "parent_post_id": post_id,
        "parent_comment_id": parent_comment_id or "",
        "comment_id": comment_id,
        "comment_text": text,
        "comment_author_username": author_username,
        "comment_author_name": author_full_name,
        "comment_author_id": author_id,
        "comment_author_pic": author_profile_pic,
        "comment_author_verified": author_is_verified
    }

def parse_follower_item(
    user: dict,
    target_username: str = "",
    target_user_id: str = "",
    relationship_type: str = "follower"
) -> Optional[Dict[str, Any]]:
    """
    Menormalisasi data profil pengikut (follower) atau following Instagram
    menjadi dictionary seragam untuk ekspor CSV & JSON.
    """
    if not user:
        return None

    uid = str(user.get("pk") or user.get("id") or user.get("pk_id", ""))
    if not uid:
        return None

    username = user.get("username", "")
    full_name = user.get("full_name", "")
    is_private = bool(user.get("is_private", False))
    is_verified = bool(user.get("is_verified", False))
    profile_pic = user.get("profile_pic_url", "")
    has_anonymous_pic = bool(user.get("has_anonymous_profile_picture", False))
    latest_reel = user.get("latest_reel_media") or 0
    has_active_story = bool(latest_reel > 0)
    profile_url = f"https://www.instagram.com/{username}/" if username else ""
    fbid = str(user.get("fbid_v2", ""))

    return {
        "row_type": relationship_type,
        "target_username": target_username,
        "target_user_id": target_user_id,
        "user_id": uid,
        "username": username,
        "full_name": full_name,
        "profile_url": profile_url,
        "is_private": is_private,
        "is_verified": is_verified,
        "has_anonymous_profile_picture": has_anonymous_pic,
        "has_active_story": has_active_story,
        "profile_pic_url": profile_pic
    }

