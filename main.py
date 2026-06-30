from __future__ import annotations
from urllib.parse import urlparse
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from database import Base, engine
from routers import auth, pages, analytics

Base.metadata.create_all(bind=engine)

_parsed = urlparse(settings.FRONTEND_URL)
_cors_origin = f"{_parsed.scheme}://{_parsed.netloc}"

app = FastAPI(title="Facebook Page Analytics API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, _cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(auth.router,      prefix=API_PREFIX)
app.include_router(pages.router,     prefix=API_PREFIX)
app.include_router(analytics.router, prefix=API_PREFIX)


@app.get("/")
def root():
    return {"status": "ok", "version": "1.0.0"}


@app.get("/health")
def health():
    return {"status": "healthy"}
