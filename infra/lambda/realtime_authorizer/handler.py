import base64
import binascii
import hashlib
import hmac
import json
import os
import time

SIGNING_ALGORITHM = "HS256"
INBOX_CHANNEL_PREFIX = "/inbox/"
CONNECT_OPERATION = "EVENT_CONNECT"
SUBSCRIBE_OPERATION = "EVENT_SUBSCRIBE"
MAX_CACHE_SECONDS = 300
JWT_SEGMENT_COUNT = 3
DENIED = {"isAuthorized": False, "ttlOverride": 0}


def handler(event: dict, context: object) -> dict:
    now = time.time()
    claims = verified_claims(event.get("authorizationToken") or "", os.environ["JWT_SECRET"], now)
    if claims is None:
        return DENIED
    request = event.get("requestContext") or {}
    subject = claims["sub"]
    operation = request.get("operation")
    is_own_inbox = request.get("channel") == f"{INBOX_CHANNEL_PREFIX}{subject}"
    is_allowed = operation == CONNECT_OPERATION or (
        operation == SUBSCRIBE_OPERATION and is_own_inbox
    )
    if not is_allowed:
        return DENIED
    return {
        "isAuthorized": True,
        "handlerContext": {"sub": subject},
        "ttlOverride": min(MAX_CACHE_SECONDS, int(claims["exp"] - now)),
    }


def verified_claims(token: str, secret: str, now: float) -> dict | None:
    segments = token.split(".")
    if len(segments) != JWT_SEGMENT_COUNT or not secret:
        return None
    encoded_header, encoded_claims, encoded_signature = segments
    try:
        header = json.loads(_base64url_decode(encoded_header))
        claims = json.loads(_base64url_decode(encoded_claims))
        signature = _base64url_decode(encoded_signature)
    except (binascii.Error, ValueError):
        return None
    signed_part = f"{encoded_header}.{encoded_claims}".encode()
    expected_signature = hmac.new(secret.encode(), signed_part, hashlib.sha256).digest()
    is_signature_valid = (
        isinstance(header, dict)
        and header.get("alg") == SIGNING_ALGORITHM
        and (hmac.compare_digest(expected_signature, signature))
    )
    if not is_signature_valid or not isinstance(claims, dict):
        return None
    expires_at = claims.get("exp")
    subject = claims.get("sub")
    is_current = isinstance(expires_at, int | float) and expires_at > now
    has_subject = isinstance(subject, str) and bool(subject)
    return claims if is_current and has_subject else None


def _base64url_decode(segment: str) -> bytes:
    padding = "=" * (-len(segment) % 4)
    return base64.urlsafe_b64decode(segment + padding)
