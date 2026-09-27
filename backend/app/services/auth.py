from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db
from app.models import User

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=True)


def hash_pin(pin: str) -> str:
    return pwd.hash(pin)


def verify_pin(pin: str, pin_hash: str) -> bool:
    return pwd.verify(pin, pin_hash)


def create_token(subject: str) -> tuple[str, int]:
    ttl = settings.JWT_TTL_HOURS * 3600
    exp = datetime.now(tz=timezone.utc) + timedelta(seconds=ttl)
    payload = {"sub": subject, "exp": exp}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALG), ttl


def ensure_owner_seeded(db: Session):
    if db.query(User).count() == 0:
        db.add(User(username="owner", pin_hash=hash_pin(settings.OWNER_PIN)))
        db.commit()


def get_current_user(
    token: str = Depends(oauth2), db: Session = Depends(get_db)
) -> User:
    creds_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALG])
        username: Optional[str] = payload.get("sub")
        if not username:
            raise creds_error
    except JWTError:
        raise creds_error
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise creds_error
    return user
