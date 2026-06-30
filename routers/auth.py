from __future__ import annotations
import logging
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import fb_client
from auth_utils import create_jwt, get_current_user
from config import settings
from database import get_db
from models import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

_oauth_states: dict[str, str] = {}


@router.get("/login")
def login():
    state = secrets.token_urlsafe(16)
    _oauth_states[state] = state
    return RedirectResponse(fb_client.build_auth_url(state))


@router.get("/callback")
def callback(code: str, state: str, db: Session = Depends(get_db)):
    if state not in _oauth_states:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    del _oauth_states[state]

    # Exchange code → short-lived token → long-lived token
    try:
        short = fb_client.exchange_code(code)
        long = fb_client.extend_token(short["access_token"])
    except Exception as exc:
        logger.error("Token exchange failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {exc}")

    access_token = long["access_token"]
    expires_in = long.get("expires_in", 5184000)  # default 60 days
    token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    # Get user identity
    try:
        me = fb_client.get_me(access_token)
    except Exception as exc:
        logger.error("Failed to get user info: %s", exc)
        raise HTTPException(status_code=502, detail=f"Could not fetch user info: {exc}")

    fb_user_id = me.get("id")
    name = me.get("name")
    email = me.get("email")

    # Upsert user
    user = db.query(User).filter(User.fb_user_id == fb_user_id).first()
    if user:
        user.access_token = access_token
        user.token_expires_at = token_expires_at
        user.name = name
        user.email = email
    else:
        user = User(
            fb_user_id=fb_user_id,
            name=name,
            email=email,
            access_token=access_token,
            token_expires_at=token_expires_at,
        )
        db.add(user)
    db.commit()
    db.refresh(user)

    response = RedirectResponse(url=settings.FRONTEND_URL)
    response.set_cookie(
        key="session",
        value=create_jwt(user.id),
        httponly=True,
        secure=settings.REDIRECT_URI.startswith("https"),
        samesite="none",
        max_age=settings.JWT_EXPIRE_HOURS * 3600,
    )
    return response


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("session")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "fb_user_id": user.fb_user_id,
        "name": user.name,
        "email": user.email,
    }
