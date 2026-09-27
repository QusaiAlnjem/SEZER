from pydantic import BaseModel, Field


class LoginIn(BaseModel):
    pin: str = Field(min_length=4, max_length=12)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class ChangePinIn(BaseModel):
    old_pin: str
    new_pin: str = Field(min_length=4, max_length=12)
