"""Supabase Storage helpers — service-key REST calls (webhooks.py pattern).

Best-effort like app/db.py: without SUPABASE_URL/SERVICE_ROLE_KEY every helper
returns None and the API keeps serving. Never logs keys or file contents.
"""
from __future__ import annotations

import logging
import os

import httpx

log = logging.getLogger("negotiator.storage")


def _env() -> tuple[str, str]:
    # the shared .env carries the PostgREST URL (…/rest/v1/); storage/auth live
    # on the bare project URL
    url = os.environ.get("SUPABASE_URL", "").rstrip("/").removesuffix("/rest/v1")
    return url, os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def store_document(path: str, data: bytes, content_type: str = "application/pdf") -> str | None:
    """Upload to the documents bucket; returns "documents/<path>" or None."""
    url, key = _env()
    if not (url and key):
        return None
    try:
        resp = httpx.post(
            f"{url}/storage/v1/object/documents/{path}",
            headers={"Authorization": f"Bearer {key}", "apikey": key,
                     "Content-Type": content_type, "x-upsert": "true"},
            content=data,
            timeout=60,
        )
        if resp.status_code in (200, 201):
            return f"documents/{path}"
        log.warning("document upload failed: %s %s", resp.status_code, resp.text[:200])
    except httpx.HTTPError as err:
        log.warning("document upload failed: %s", err)
    return None


def store_recording(call_id: str, audio: bytes) -> str | None:
    """Upload call audio to the recordings bucket; returns "recordings/<id>.mp3"
    (the shape set_call_recording stores) or None."""
    url, key = _env()
    if not (url and key):
        return None
    path = f"{call_id}.mp3"
    try:
        resp = httpx.post(
            f"{url}/storage/v1/object/recordings/{path}",
            headers={"Authorization": f"Bearer {key}", "apikey": key,
                     "Content-Type": "audio/mpeg", "x-upsert": "true"},
            content=audio,
            timeout=60,
        )
        if resp.status_code in (200, 201):
            return f"recordings/{path}"
        log.warning("recording upload failed: %s %s", resp.status_code, resp.text[:200])
    except httpx.HTTPError as err:
        log.warning("recording upload failed: %s", err)
    return None


def store_authorization(case_id: str, audio: bytes, content_type: str = "audio/webm") -> str | None:
    """Upload the patient's recorded authorization to the authorizations bucket;
    returns "authorizations/<case_id>.<ext>" or None. One clip per case (upsert)."""
    url, key = _env()
    if not (url and key):
        return None
    ext = "mp3" if content_type == "audio/mpeg" else "webm"
    path = f"{case_id}.{ext}"
    try:
        resp = httpx.post(
            f"{url}/storage/v1/object/authorizations/{path}",
            headers={"Authorization": f"Bearer {key}", "apikey": key,
                     "Content-Type": content_type, "x-upsert": "true"},
            content=audio,
            timeout=60,
        )
        if resp.status_code in (200, 201):
            return f"authorizations/{path}"
        log.warning("authorization upload failed: %s %s", resp.status_code, resp.text[:200])
    except httpx.HTTPError as err:
        log.warning("authorization upload failed: %s", err)
    return None


def sign_url(storage_path: str, expires_in: int = 3600) -> str | None:
    """Signed URL for a stored object; storage_path includes the bucket
    (e.g. "recordings/<call_id>.mp3", the shape set_call_recording stores)."""
    url, key = _env()
    if not (url and key and storage_path):
        return None
    try:
        resp = httpx.post(
            f"{url}/storage/v1/object/sign/{storage_path}",
            headers={"Authorization": f"Bearer {key}", "apikey": key},
            json={"expiresIn": expires_in},
            timeout=30,
        )
        if resp.status_code == 200:
            signed = resp.json().get("signedURL")
            if signed:
                return f"{url}/storage/v1{signed}"
        log.warning("sign failed for %s: %s %s", storage_path, resp.status_code, resp.text[:200])
    except (httpx.HTTPError, ValueError) as err:
        log.warning("sign failed for %s: %s", storage_path, err)
    return None
