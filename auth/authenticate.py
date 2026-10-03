from fastapi import Depends, HTTPException, status, Security
from fastapi.security import OAuth2PasswordBearer, SecurityScopes
from auth.jwt_handler import verify_access_token

# Define a URL de emissão de token e declara os escopos da API (Discovery)
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/oauth/token",
    scopes={
        "appointments:read": "Ler dados de consultas e vagas",
        "appointments:write": "Criar, editar ou excluir consultas"
    }
)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """Dependency Injection que decodifica e retorna os claims sem validar escopos."""
    return verify_access_token(token)


async def get_current_user_with_scopes(
        security_scopes: SecurityScopes,
        token: str = Depends(oauth2_scheme)
) -> dict:
    """
    Security Gate: Decodifica o JWT e garante que o cliente possua TODOS
    os escopos OAuth 2.0 requeridos pela rota.
    """
    if security_scopes.scopes:
        authenticate_value = f'Bearer scope="{security_scopes.scope_str}"'
    else:
        authenticate_value = "Bearer"

    payload = verify_access_token(token)

    # Extrai os escopos do token (string separada por espaços)
    token_scopes = payload.get("scope", "").split()

    # Verifica a presença de todos os escopos obrigatórios da rota alvo
    for scope in security_scopes.scopes:
        if scope not in token_scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissão insuficiente: escopos ausentes no token",
                headers={"WWW-Authenticate": authenticate_value},
            )
    return payload