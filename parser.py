from typing import Any, Dict, List, Optional

def extract_tweet_from_result(tweet_result: dict, row_type: str = "main_tweet", parent_tweet_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Safely parses a Twitter GraphQL tweet result object into a clean dictionary.
    """
    if not tweet_result:
        return None
        
    # Handle TweetWithVisibilityResults or regular Tweet
    typename = tweet_result.get("__typename", "")
    if typename == "TweetWithVisibilityResults":
        tweet_data = tweet_result.get("tweet", {})
    else:
        tweet_data = tweet_result

    legacy = tweet_data.get("legacy")
    if not legacy:
        return None

    tweet_id = tweet_data.get("rest_id") or legacy.get("id_str", "")
    if not tweet_id:
        return None

    # Extract user details
    core = tweet_data.get("core", {})
    user_result = core.get("user_results", {}).get("result", {})
    if not user_result:
        user_result = tweet_data.get("user_results", {}).get("result", {})
    
    if user_result.get("__typename") == "UserWithVisibilityResults":
        user_data = user_result.get("user", {})
    else:
        user_data = user_result
        
    user_legacy = user_data.get("legacy", {}) or user_result.get("legacy", {})
    user_core = user_data.get("core", {}) or user_result.get("core", {})
    user_counts = user_data.get("relationship_counts", {}) or user_result.get("relationship_counts", {})
    user_rest_id = user_data.get("rest_id") or user_result.get("rest_id", "") or user_data.get("id", "")
    
    screen_name = (
        user_core.get("screen_name") or 
        user_legacy.get("screen_name") or 
        user_data.get("screen_name", "")
    )
    name = (
        user_core.get("name") or 
        user_legacy.get("name") or 
        user_data.get("name", "")
    )
    user_bio = (
        user_data.get("profile_bio", {}).get("description") or 
        user_legacy.get("description", "")
    )
    user_followers = (
        user_counts.get("followers") or 
        user_legacy.get("followers_count", 0) or 0
    )
    user_following = (
        user_counts.get("following") or 
        user_legacy.get("friends_count", 0) or 0
    )
    user_location = (
        user_data.get("location", {}).get("location") or 
        user_legacy.get("location", "") or ""
    )
    user_avatar = (
        user_data.get("avatar", {}).get("image_url") or 
        user_legacy.get("profile_image_url_https", "") or ""
    )
    user_verified = bool(
        user_data.get("is_blue_verified", False) or 
        user_data.get("verification", {}).get("is_blue_verified", False) or 
        user_legacy.get("verified", False)
    )

    # Media
    media_urls = []
    media_types = []
    extended_entities = legacy.get("extended_entities", {}) or legacy.get("entities", {})
    for m in extended_entities.get("media", []):
        m_type = m.get("type", "photo")
        media_types.append(m_type)
        m_url = m.get("media_url_https") or m.get("media_url") or m.get("expanded_url", "")
        if m_url:
            media_urls.append(m_url)

    # Hashtags
    hashtags = [h.get("text", "") for h in legacy.get("entities", {}).get("hashtags", []) if h.get("text")]

    # URLs
    urls = [u.get("expanded_url", u.get("url", "")) for u in legacy.get("entities", {}).get("urls", []) if u.get("expanded_url") or u.get("url")]

    # Views
    views_data = tweet_data.get("views", {})
    views_count = views_data.get("count", "")

    # In reply to / quote
    in_reply_to_str = legacy.get("in_reply_to_status_id_str")
    is_reply = bool(in_reply_to_str or row_type == "reply")
    reply_to_id = in_reply_to_str if in_reply_to_str else (parent_tweet_id or None)
    
    quoted_status_id = legacy.get("quoted_status_id_str")
    is_quote = bool(legacy.get("is_quote_status", False) or quoted_status_id)

    text = legacy.get("full_text") or legacy.get("text", "")
    tweet_url = f"https://x.com/{screen_name}/status/{tweet_id}" if screen_name else f"https://x.com/i/status/{tweet_id}"

    return {
        "row_type": row_type,
        "parent_tweet_id": reply_to_id,
        "tweet_id": str(tweet_id),
        "url": tweet_url,
        "created_at": str(legacy.get("created_at", "")),
        "text": text,
        "lang": legacy.get("lang", ""),
        "likes": legacy.get("favorite_count", 0),
        "retweets": legacy.get("retweet_count", 0),
        "replies": legacy.get("reply_count", 0),
        "quotes": legacy.get("quote_count", 0),
        "bookmarks": legacy.get("bookmark_count", 0),
        "views": views_count,
        "is_reply": is_reply,
        "in_reply_to_tweet_id": reply_to_id,
        "is_quote": is_quote,
        "quoted_tweet_id": quoted_status_id,
        "user_id": str(user_rest_id),
        "username": screen_name,
        "name": name,
        "user_bio": user_bio,
        "user_followers_count": user_followers,
        "user_following_count": user_following,
        "user_verified": user_verified,
        "user_location": user_location,
        "user_avatar": user_avatar,
        "hashtags": ", ".join(hashtags),
        "media_types": ", ".join(media_types),
        "media_urls": ", ".join(media_urls),
        "urls": ", ".join(urls),
    }

def parse_tweet(tweet_obj: Any, row_type: str = "main_tweet", parent_tweet_id: Optional[str] = None) -> Dict[str, Any]:
    """Compatibility wrapper that handles either dict responses or objects."""
    if isinstance(tweet_obj, dict):
        res = extract_tweet_from_result(tweet_obj, row_type=row_type, parent_tweet_id=parent_tweet_id)
        return res if res else {}
    
    # If it's a Twikit Tweet object
    user = getattr(tweet_obj, "user", None)
    return {
        "row_type": row_type,
        "parent_tweet_id": parent_tweet_id,
        "tweet_id": str(getattr(tweet_obj, "id", "")),
        "url": f"https://x.com/{getattr(user, 'screen_name', '')}/status/{getattr(tweet_obj, 'id', '')}",
        "created_at": str(getattr(tweet_obj, "created_at", "")),
        "text": getattr(tweet_obj, "full_text", None) or getattr(tweet_obj, "text", ""),
        "lang": getattr(tweet_obj, "lang", ""),
        "likes": getattr(tweet_obj, "favorite_count", 0) or 0,
        "retweets": getattr(tweet_obj, "retweet_count", 0) or 0,
        "replies": getattr(tweet_obj, "reply_count", 0) or 0,
        "quotes": getattr(tweet_obj, "quote_count", 0) or 0,
        "bookmarks": getattr(tweet_obj, "bookmark_count", 0) or 0,
        "views": getattr(tweet_obj, "view_count", "") or "",
        "is_reply": bool(getattr(tweet_obj, "in_reply_to", None) or row_type == "reply"),
        "in_reply_to_tweet_id": str(getattr(tweet_obj, "in_reply_to", "")) or parent_tweet_id,
        "is_quote": bool(getattr(tweet_obj, "is_quote_status", False)),
        "quoted_tweet_id": None,
        "user_id": str(getattr(user, "id", "")),
        "username": getattr(user, "screen_name", ""),
        "name": getattr(user, "name", ""),
        "user_bio": getattr(user, "description", ""),
        "user_followers_count": getattr(user, "followers_count", 0),
        "user_following_count": getattr(user, "following_count", 0),
        "user_verified": bool(getattr(user, "verified", False) or getattr(user, "is_blue_verified", False)),
        "user_location": getattr(user, "location", ""),
        "user_avatar": getattr(user, "profile_image_url", ""),
        "hashtags": "",
        "media_types": "",
        "media_urls": "",
        "urls": "",
    }
