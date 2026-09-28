from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.schemas import LoginIn, TokenOut
from app.services.auth import create_token, get_current_user, verify_owner_pin

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(form: OAuth2PasswordRequestForm = Depends()):
    """OAuth2 form login for compatibility. `password` field carries the PIN."""
    if not verify_owner_pin(form.password):
        raise HTTPException(status_code=401, detail="PIN غير صحيح")
    token, ttl = create_token()
    return TokenOut(access_token=token, expires_in=ttl)


@router.post("/pin", response_model=TokenOut)
def login_pin(body: LoginIn):
    """Simple PIN-only endpoint used by the mobile UI."""
    if not verify_owner_pin(body.pin):
        raise HTTPException(status_code=401, detail="PIN غير صحيح")
    token, ttl = create_token()
    return TokenOut(access_token=token, expires_in=ttl)


@router.get("/me")
def me(user: str = Depends(get_current_user)):
    return {"username": user}
