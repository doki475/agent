from __future__ import annotations

import os
import secrets

BACKEND_BASE_URL = os.getenv("TPA_BACKEND_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
FRONTEND_PORT = int(os.getenv("TPA_FRONTEND_PORT", "8080"))
STORAGE_SECRET = os.getenv("TPA_STORAGE_SECRET") or secrets.token_urlsafe(32)
API_PREFIX = "/api/v1"
WS_URL = BACKEND_BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + f"{API_PREFIX}/ws/chat"
