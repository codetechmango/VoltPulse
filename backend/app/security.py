import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import secrets

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "smart-electricity-dev-secret-change-me")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
HARDWARE_API_KEY = os.getenv("HARDWARE_API_KEY", "voltpulse-hw-secret-key-2026")
HARDWARE_DEFAULT_USER_ID = int(os.getenv("HARDWARE_USER_ID", "5"))

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    iterations = 100_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def verify_password(plain_password: str, password_hash: str) -> bool:
    if not password_hash:
        return False
    try:
        algorithm, iter_str, salt, digest = password_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False

        iterations = int(iter_str)
        computed = hashlib.pbkdf2_hmac(
            "sha256",
            plain_password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        ).hex()
        return hmac.compare_digest(computed, digest)
    except (TypeError, ValueError):
        return False


def _encode_jwt(payload: dict[str, str | int]) -> str:
    header = {"alg": ALGORITHM, "typ": "JWT"}
    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        f"{header_segment}.{payload_segment}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature_segment = _b64url_encode(signature)
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def _decode_jwt(token: str) -> dict[str, str | int]:
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token") from exc

    expected_signature = hmac.new(
        SECRET_KEY.encode("utf-8"),
        f"{header_segment}.{payload_segment}".encode("utf-8"),
        hashlib.sha256,
    ).digest()
    actual_signature = _b64url_decode(signature_segment)

    if not hmac.compare_digest(expected_signature, actual_signature):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")

    payload = json.loads(_b64url_decode(payload_segment).decode("utf-8"))
    exp = payload.get("exp")
    if isinstance(exp, int) and exp < int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication token has expired")

    return payload


def create_access_token(data: dict[str, str], expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": int(expire.timestamp())})
    return _encode_jwt(to_encode)


def decode_access_token(token: str) -> dict[str, str]:
    payload = _decode_jwt(token)
    return {key: str(value) for key, value in payload.items()}


def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    # 1. Check persistent hardware API Key from X-API-Key or Bearer header
    api_key = request.headers.get("x-api-key") or request.headers.get("X-API-Key")
    if (api_key and api_key == HARDWARE_API_KEY) or (token and token == HARDWARE_API_KEY):
        hw_user_id_str = request.headers.get("x-user-id") or request.headers.get("X-User-ID")
        target_id = int(hw_user_id_str) if hw_user_id_str and hw_user_id_str.isdigit() else HARDWARE_DEFAULT_USER_ID
        user = db.query(User).filter(User.id == target_id).first()
        if not user:
            user = db.query(User).filter(User.role == "user").first()
        if not user:
            user = db.query(User).first()
        if user:
            setattr(user, "is_hardware", True)
            return user

    # 2. Check JWT Token
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide Bearer token or X-API-Key header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(token)
    subject = payload.get("sub")

    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token")

    try:
        user_id = int(subject)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authentication token") from exc

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists")

    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only admin can perform this action")
    return current_user
