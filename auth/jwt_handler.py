import os
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from fastapi import HTTPException, status
from jose import jwt, JWTError

# Se a variável de ambiente não existir, ele assume a string padrão
SECRET_KEY = os.getenv("SECRET_KEY", "CHAVE_SECRETA_CLINICA_API_PRODUCAO")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

def create_access_token(user_id: str, role: str, mfa_verified: bool = False, scope: str = "") -> str:
    """Gera um JWT assinado com claims essenciais para RBAC e MFA."""
    payload = {
        "sub": user_id,
        "role": role,
        "mfa_verified": mfa_verified,
        "scope": scope,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_access_token(token: str) -> Dict[str, Any]:
    """Decodifica e valida a assinatura e expiração do JWT."""
    try:
        decoded_token = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        if decoded_token.get("exp") < time.time():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expirado. Autentique-se novamente."
            )
        return decoded_token
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou assinatura corrompida."
        )