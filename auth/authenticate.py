from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from auth.jwt_handler import verify_access_token

# Define a URL de onde as credenciais serão recuperadas
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/user/login")

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Dependency Injection que decodifica e retorna os claims do usuário autenticado."""
    return verify_access_token(token)