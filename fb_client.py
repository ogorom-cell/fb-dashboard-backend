from __future__ import annotations
from urllib.parse import urlencode
import httpx
from config import settings

BASE = f"https://graph.facebook.com/{settings.FB_API_VERSION}"
AUTH_URL = "https://www.facebook.com/dialog/oauth"
TOKEN_URL = f"https://graph.facebook.com/{settings.FB_API_VERSION}/oauth/access_token"
SCOPES = "pages_show_list,pages_read_engagement,read_insights,business_management"


def build_auth_url(state: str) -> str:
    return f"{AUTH_URL}?" + urlencode({
        "client_id": settings.FB_APP_ID,
        "redirect_uri": settings.REDIRECT_URI,
        "scope": SCOPES,
        "state": state,
        "response_type": "code",
    })


def exchange_code(code: str) -> dict:
    resp = httpx.get(TOKEN_URL, params={
        "client_id": settings.FB_APP_ID,
        "redirect_uri": settings.REDIRECT_URI,
        "client_secret": settings.FB_APP_SECRET,
        "code": code,
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()


def extend_token(short_token: str) -> dict:
    """Exchange short-lived (1h) token for long-lived (60-day) token."""
    resp = httpx.get(TOKEN_URL, params={
        "grant_type": "fb_exchange_token",
        "client_id": settings.FB_APP_ID,
        "client_secret": settings.FB_APP_SECRET,
        "fb_exchange_token": short_token,
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()


def get_me(token: str) -> dict:
    resp = httpx.get(f"{BASE}/me", params={
        "fields": "id,name,email",
        "access_token": token,
    }, timeout=10)
    resp.raise_for_status()
    return resp.json()


def get_pages(user_token: str) -> list[dict]:
    """Return all pages the user can access, including Business Manager pages."""
    seen: set[str] = set()
    pages: list[dict] = []

    # Direct page roles (/me/accounts)
    try:
        resp = httpx.get(f"{BASE}/me/accounts", params={
            "fields": "id,name,category,fan_count,picture{url},access_token",
            "access_token": user_token,
        }, timeout=15)
        resp.raise_for_status()
        for p in resp.json().get("data", []):
            if p["id"] not in seen:
                seen.add(p["id"])
                pages.append(p)
    except Exception:
        pass

    # Business Manager pages
    try:
        biz_resp = httpx.get(f"{BASE}/me/businesses", params={
            "fields": "id,name",
            "access_token": user_token,
        }, timeout=15)
        if biz_resp.status_code == 200:
            for biz in biz_resp.json().get("data", []):
                biz_id = biz["id"]
                for edge in ("owned_pages", "client_pages"):
                    try:
                        pr = httpx.get(f"{BASE}/{biz_id}/{edge}", params={
                            "fields": "id,name,category,fan_count,picture{url},access_token",
                            "access_token": user_token,
                        }, timeout=15)
                        if pr.status_code == 200:
                            for p in pr.json().get("data", []):
                                if p["id"] not in seen and p.get("access_token"):
                                    seen.add(p["id"])
                                    pages.append(p)
                    except Exception:
                        pass
    except Exception:
        pass

    return pages


def get_page_token(user_token: str, page_id: str) -> str:
    """Fetch the permanent page access token for a specific page."""
    pages = get_pages(user_token)
    for page in pages:
        if page["id"] == page_id:
            return page["access_token"]
    raise ValueError(f"Page {page_id} not found or user is not an admin")


def get_page_insights(page_token: str, page_id: str, since: str, until: str, period: str = "day") -> dict:
    # Request metrics in small groups so a bad metric doesn't block the rest
    day_metric_groups = [
        ["page_impressions", "page_impressions_unique"],
        ["page_impressions_organic", "page_impressions_paid"],
        ["page_fan_adds"],
        ["page_post_engagements"],
        ["page_video_views"],
        ["page_daily_video_ad_break_earnings", "page_daily_video_ad_break_ad_impressions"],
    ]
    all_data: list = []
    for group in day_metric_groups:
        try:
            resp = httpx.get(
                f"{BASE}/{page_id}/insights",
                params={
                    "metric": ",".join(group),
                    "period": period,
                    "since": since,
                    "until": until,
                    "access_token": page_token,
                },
                timeout=30,
            )
            if resp.status_code == 200:
                all_data.extend(resp.json().get("data", []))
        except Exception:
            pass

    # page_fans requires period=lifetime
    try:
        fans_resp = httpx.get(
            f"{BASE}/{page_id}/insights",
            params={
                "metric": "page_fans",
                "period": "lifetime",
                "access_token": page_token,
            },
            timeout=15,
        )
        if fans_resp.status_code == 200:
            all_data.extend(fans_resp.json().get("data", []))
    except Exception:
        pass

    return {"data": all_data}


def get_page_posts(page_token: str, page_id: str, limit: int = 20) -> list[dict]:
    resp = httpx.get(
        f"{BASE}/{page_id}/posts",
        params={
            "fields": "id,message,story,created_time,permalink_url,attachments{media_type,title}",
            "limit": limit,
            "access_token": page_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    posts = resp.json().get("data", [])

    for post in posts:
        try:
            ins = httpx.get(
                f"{BASE}/{post['id']}/insights",
                params={
                    "metric": "post_impressions_unique,post_engaged_users,post_reactions_like_total,post_video_views",
                    "access_token": page_token,
                },
                timeout=10,
            )
            if ins.status_code == 200:
                post["insights"] = {
                    item["name"]: (item["values"][0]["value"] if item.get("values") else 0)
                    for item in ins.json().get("data", [])
                }
        except Exception:
            post["insights"] = {}

    return posts
