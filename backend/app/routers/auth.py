from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import LoginIn, TokenOut, ChangePinIn
from app.services.auth import (
    create_token,
    ensure_owner_seeded,
    get_current_user,
    hash_pin,
    verify_pin,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 form login for compatibility. `password` field carries the PIN."""
    ensure_owner_seeded(db)
    # Avoid using Python `or` inside the SQLAlchemy filter expression.
    # Use the provided username (usually 'owner') to find the user.
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_pin(form.password, user.pin_hash):
        raise HTTPException(status_code=401, detail="PIN غير صحيح")
    token, ttl = create_token(user.username)
    return TokenOut(access_token=token, expires_in=ttl)


@router.post("/pin", response_model=TokenOut)
def login_pin(body: LoginIn, db: Session = Depends(get_db)):
    """Simple PIN-only endpoint used by the mobile UI."""
    ensure_owner_seeded(db)
    user = db.query(User).filter(User.username == "owner").first()
    if not user or not verify_pin(body.pin, user.pin_hash):
        raise HTTPException(status_code=401, detail="PIN غير صحيح")
    token, ttl = create_token(user.username)
    return TokenOut(access_token=token, expires_in=ttl)


@router.post("/change-pin", response_model=TokenOut)
def change_pin(body: ChangePinIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not verify_pin(body.old_pin, user.pin_hash):
        raise HTTPException(status_code=401, detail="PIN القديم غير صحيح")
    user.pin_hash = hash_pin(body.new_pin)
    db.commit()
    token, ttl = create_token(user.username)
    return TokenOut(access_token=token, expires_in=ttl)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"username": user.username}
