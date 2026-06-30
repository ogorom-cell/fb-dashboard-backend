from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
import fb_client
from auth_utils import get_current_user
from database import get_db
from models import User

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _get_page_token(user: User, page_id: str) -> str:
    try:
        return fb_client.get_page_token(user.access_token, page_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Could not fetch page token: {exc}")


@router.get("/stats")
def get_stats(
    page_id: str = Query(...),
    since: str = Query(..., description="Unix timestamp or YYYY-MM-DD"),
    until: str = Query(..., description="Unix timestamp or YYYY-MM-DD"),
    period: str = Query("day", description="day | week | month | lifetime"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page_token = _get_page_token(user, page_id)
    try:
        data = fb_client.get_page_insights(page_token, page_id, since, until, period)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Insights API error: {exc}")

    # Reshape: list of metric objects → {metric_name: [{end_time, value}]}
    metrics: dict = {}
    for item in data.get("data", []):
        metrics[item["name"]] = item.get("values", [])

    return {"metrics": metrics, "raw": data}


@router.get("/posts")
def get_posts(
    page_id: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    page_token = _get_page_token(user, page_id)
    try:
        posts = fb_client.get_page_posts(page_token, page_id, limit)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Posts API error: {exc}")

    return {"items": posts, "total": len(posts)}
