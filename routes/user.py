from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from auth.hash_password import HashPassword
from auth.jwt_handler import create_access_token
from database.users import users_db

router = APIRouter(prefix="/user", tags=["User"])

@router.post("/login")
async def sign_user_in(user: OAuth2PasswordRequestForm = Depends()) -> dict:
    user_exist = users_db.get(user.username)
    if not user_exist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

    # Valida senha Bcrypt
    if not HashPassword.verify_password(user.password, user_exist["password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas.")

    # MFA para o Administrador
    if user_exist["role"] == "admin":
        return {
            "mfa_required": True,
            "message": "Usuário admin requer autenticação multifator (MFA). Por favor, forneça o código."
        }

    scopes_string = " ".join(user.scopes) if user.scopes else ""
    access_token = create_access_token(user_id=user_exist["id"], role=user_exist["role"], scope=scopes_string)

    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/login/mfa-verify")
async def verify_mfa(username: str, mfa_code: str) -> dict:
    user_exist = users_db.get(username)
    if not user_exist or user_exist["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário não elegível para MFA.")

    if user_exist.get("mfa_secret") != mfa_code:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Código MFA inválido.")

    # Emite JWT do Admin confirmando a verificação de duplo fator (mfa_verified=True)
    access_token = create_access_token(user_id=user_exist["id"], role=user_exist["role"], mfa_verified=True)
    return {"access_token": access_token, "token_type": "bearer"}