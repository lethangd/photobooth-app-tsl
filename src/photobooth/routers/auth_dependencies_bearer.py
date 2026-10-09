from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError
from pydantic import BaseModel

from ..services import credentials

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60
USERS = {"admin": "Admin"}


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: str


class User(BaseModel):
    username: str
    full_name: str | None = None
    # disabled: Union[bool, None] = None # functionality not used currently.


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/admin/auth/token")


def get_user(user_id: str) -> User | None:
    if user_id in USERS:
        return User(username=user_id, full_name=USERS[user_id])

    return None


def authenticate_user(user_id: str, password: str) -> User | None:
    user = get_user(user_id)
    if not user:
        return None
    # the password is kept hashed in .env, see services/credentials.py
    if not credentials.verify_admin_password(password):
        return None
    return user


def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.now(UTC) + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, credentials.token_secret(), algorithm=ALGORITHM)
    return encoded_jwt


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, credentials.token_secret(), algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError as exc:
        raise credentials_exception from exc

    user = get_user(user_id=token_data.username)
    if user is None:
        raise credentials_exception
    return user


async def get_current_active_user(current_user: Annotated[User, Depends(get_current_user)]):
    return current_user
