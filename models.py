from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime
from database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    fb_user_id = Column(String, unique=True, nullable=False)
    name = Column(Text)
    email = Column(Text)
    access_token = Column(Text, nullable=False)   # long-lived user token (60 days)
    token_expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=utcnow)
