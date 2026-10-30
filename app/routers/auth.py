from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from app.deps import DB, CurrentUser
from app.schemas import Token, UserCreate, UserOut
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED,
             summary="Self-register (always gets the 'staff' role)")
def register(data: UserCreate, db: DB):
    return auth_service.create_user(db, data.username, data.email, data.password)


@router.post("/login", response_model=Token, summary="Login and receive a JWT")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DB):
    return Token(access_token=auth_service.login(db, form.username, form.password))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return user
