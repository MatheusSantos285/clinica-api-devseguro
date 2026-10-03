from fastapi import APIRouter, Depends, HTTPException, status, Form
from fastapi.security import OAuth2PasswordRequestForm
from auth.hash_password import HashPassword
from auth.jwt_handler import create_access_token
from database.users import users_db

# Router sem prefixo para permitir rotas padronizadas /oauth/token e /user/*
router = APIRouter(tags=["Auth & Users"])


@router.post("/user/login")
async def sign_user_in(user: OAuth2PasswordRequestForm = Depends()) -> dict:
    user_exist = users_db.get(user.username)
    if not user_exist or user_exist.get("type") == "m2m":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuário não encontrado.")

    if not HashPassword.verify_password(user.password, user_exist["password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais inválidas.")

    if user_exist["role"] == "admin":
        return {
            "mfa_required": True,
            "message": "Usuário admin requer autenticação multifator (MFA). Por favor, forneça o código."
        }

    # Defesa de Escopo: Concede escopos totais por padrão aos usuários humanos caso não solicitem explícito,
    # garantindo a retrocompatibilidade com os testes do Exercício 6.
    if not user.scopes:
        scopes_string = "appointments:read appointments:write"
    else:
        scopes_string = " ".join(user.scopes)

    access_token = create_access_token(user_id=user_exist["id"], role=user_exist["role"], scope=scopes_string)
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/user/login/mfa-verify")
async def verify_mfa(username: str, mfa_code: str) -> dict:
    user_exist = users_db.get(username)
    if not user_exist or user_exist["role"] != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuário não elegível para MFA.")

    if user_exist.get("mfa_secret") != mfa_code:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Código MFA inválido.")

    access_token = create_access_token(
        user_id=user_exist["id"],
        role=user_exist["role"],
        mfa_verified=True,
        scope="appointments:read appointments:write"
    )
    return {"access_token": access_token, "token_type": "bearer"}


# EXERCÍCIO 7: Emissão de Token M2M (Client Credentials Grant)
@router.post("/oauth/token")
async def oauth_token(
        grant_type: str = Form(...),
        client_id: str = Form(...),
        client_secret: str = Form(...)
) -> dict:
    if grant_type != "client_credentials":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Grant type não suportado.")

    client = users_db.get(client_id)
    if not client or client.get("type") != "m2m":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Cliente M2M não encontrado.")

    if not HashPassword.verify_password(client_secret, client["password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciais de cliente inválidas.")

    scopes_concedidos = " ".join(client.get("scopes", []))

    access_token = create_access_token(
        user_id=client["id"],
        role=client.get("role", "m2m"),
        scope=scopes_concedidos
    )
    return {"access_token": access_token, "token_type": "bearer"}