from fastapi import APIRouter, Depends, HTTPException, status
from auth.authenticate import get_current_user

router = APIRouter(prefix="/admin", tags=["Admin"])

async def require_admin(claims: dict = Depends(get_current_user)) -> dict:
    """Garante que o usuário possui o papel admin E que passou pelo MFA."""
    if claims.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a Administradores do sistema (BFLA Block)."
        )
    if not claims.get("mfa_verified"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Ação requer autenticação com Múltiplo Fator (MFA)."
        )
    return claims

@router.get("/dashboard")
async def get_admin_dashboard(claims: dict = Depends(require_admin)):
    """Rota protegida para Administradores."""
    return {
        "message": "Bem-vindo ao Painel de Controle (Admin).",
        "admin_id": claims.get("sub")
    }