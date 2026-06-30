from __future__ import annotations
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import fb_client
from auth_utils import get_current_user
from database import get_db
from models import User

router = APIRouter(prefix="/pages", tags=["pages"])


@router.get("")
def list_pages(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    pages = fb_client.get_pages(user.access_token)
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "category": p.get("category"),
            "fan_count": p.get("fan_count", 0),
            "picture": p.get("picture", {}).get("data", {}).get("url"),
        }
        for p in pages
    ]
