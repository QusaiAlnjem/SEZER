import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.core.config import settings

OWNER = "owner"
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=True)


def verify_owner_pin(pin: str) -> bool:
    # constant-time: a PIN mismatch shouldn't be timeable against OWNER_PIN
    return secrets.compare_digest(pin, settings.OWNER_PIN)


def create_token(subject: str = OWNER) -> tuple[str, int]:
    ttl = settings.JWT_TTL_HOURS * 3600
    exp = datetime.now(tz=timezone.utc) + timedelta(seconds=ttl)
    payload = {"sub": subject, "exp": exp}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG), ttl


def get_current_user(token: str = Depends(oauth2)) -> str:
    creds_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
        username: Optional[str] = payload.get("sub")
        if username != OWNER:
            raise creds_error
    except JWTError:
        raise creds_error
    return username
