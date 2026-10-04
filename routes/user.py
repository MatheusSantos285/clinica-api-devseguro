from fastapi import APIRouter, Depends, HTTPException, status, Form, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select
from auth.hash_password import HashPassword
from auth.jwt_handler import create_access_token
from config.rate_limiter import limiter
from database.connection import get_session
from models.users import User

router = APIRouter(tags=["Auth & Users"])

@router.post("/user/login")
@limiter.limit("5/minute")
async def sign_user_in(
        request: Request,
        user: OAuth2PasswordRequestForm = Depends(),
        session: Session = Depends(get_session)
) -> dict:
    user_exist = session.exec(select(User).where(User.email == user.username)).first()

    if not user_exist or user_exist.is_m2m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

    if not HashPassword.verify_password(user.password, user_exist.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas.")

    if user_exist.role == "admin":
        return {
            "mfa_required": True,
            "message": "Usuário admin requer MFA. Por favor, forneça o código."
        }

    scopes_string = "appointments:read appointments:write" if not user.scopes else " ".join(user.scopes)

    access_token = create_access_token(user_id=user_exist.id, role=user_exist.role, scope=scopes_string)
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/user/login/mfa-verify")
async def verify_mfa(
        username: str,
        mfa_code: str,
        session: Session = Depends(get_session)
) -> dict:
    user_exist = session.exec(select(User).where(User.email == username)).first()

    if not user_exist or user_exist.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário não elegível para MFA.")

    if user_exist.mfa_secret != mfa_code:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Código MFA inválido.")

    access_token = create_access_token(
        user_id=user_exist.id, role=user_exist.role,
        mfa_verified=True, scope="appointments:read appointments:write"
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/oauth/token")
async def oauth_token(
        grant_type: str = Form(...), client_id: str = Form(...), client_secret: str = Form(...),
        session: Session = Depends(get_session)
) -> dict:
    if grant_type != "client_credentials":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Grant type não suportado.")

    client = session.exec(select(User).where(User.id == client_id)).first()

    if not client or not client.is_m2m:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cliente M2M não encontrado.")

    if not HashPassword.verify_password(client_secret, client.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas.")

    access_token = create_access_token(
        user_id=client.id, role=client.role, scope=client.scopes or ""
    )
    return {"access_token": access_token, "token_type": "bearer"}