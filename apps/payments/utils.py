"""eSewa / Khalti signing helpers."""
import base64
import hashlib
import hmac


def hmac_sha256_base64(secret: str, message: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def safe_compare(a: str, b: str) -> bool:
    return hmac.compare_digest(str(a), str(b))


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")
