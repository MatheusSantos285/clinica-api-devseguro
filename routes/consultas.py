import re
from fastapi import APIRouter, HTTPException, status, Path, Request, Depends, Security, Query
from fastapi.responses import HTMLResponse
from typing import List
from fastapi.templating import Jinja2Templates
from config.rate_limiter import limiter
from database.consultas import consultas_db
from sqlmodel import Session, select
from database.connection import get_session
from models.consultas import ConsultaCreate, ConsultaResponse, Consulta
from auth.authenticate import get_current_user, get_current_user_with_scopes

# Concentra os controladores e a definição dos endpoints RESTful
router = APIRouter(prefix="/consultas", tags=["Consultas"])
# Configuração do Jinja2 apontando para o diretório de templates
templates = Jinja2Templates(directory="templates")

# EXERCÍCIO 9 - DEPENDÊNCIA CENTRALIZADA CONTRA BOLA (IDOR)
def get_owned_consulta(id: int = Path(...), current_user: dict = Depends(get_current_user), session: Session = Depends(get_session)) -> Consulta:
    """
    Busca a consulta e verifica a propriedade (Ownership).
    Mitiga a enumeração de IDs devolvendo 404 em vez de 403.
    """
    consulta = session.exec(select(Consulta).where(Consulta.id == id)).first()
    if not consulta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")

    # Validação de ownership: Se for médico, só acessa os seus próprios pacientes.
    if current_user.get("role") == "medico" and consulta.medico_id != current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")

    return consulta

# CÓDIGO ANTERIOR (EVIDÊNCIA EXERCÍCIO 8)
#@router.get("/", response_model=List[ConsultaResponse])
#async def listar_consultas():
#    """Retorna a lista de todas as consultas agendadas."""
#    return list(consultas_db.values())

@router.get("/", response_model=List[ConsultaResponse])
@limiter.limit("60/minute")
async def listar_consultas(request: Request, current_user: dict = Depends(get_current_user), session: Session = Depends(get_session)):
    """Retorna a lista de consultas filtrada com base no papel e propriedade do usuário."""

    # Se o usuário for um administrador, ele tem privilégios para ver a agenda global
    if current_user.get("role") == "admin":
        return session.exec(select(Consulta)).all()
    # Se for um médico, filtramos a lista devolvendo APENAS as consultas dele
    elif current_user.get("role") == "medico":
        return session.exec(select(Consulta).where(Consulta.medico_id == current_user.get("sub"))).all()

    # Recepcionistas ou outros papéis podem ter lógicas específicas ou serem bloqueados
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Acesso negado. Você não tem permissão para listar consultas."
    )

# CÓDIGO ANTERIOR (EVIDÊNCIA EXERCÍCIO 8)
#@router.get("/agenda-html", response_class=HTMLResponse)
#async def renderizar_agenda(request: Request):
#    """
#    Rota HTML: Renderiza a lista de consultas para a recepção,
#    utilizando Jinja2 e garantindo o mascaramento do campo interno.
#    """
#    consultas_lista = list(consultas_db.values())
#    return templates.TemplateResponse(
#        request=request,
#        name="agenda.html",
#        context={"consultas": consultas_lista}
#    )

@router.get("/agenda-html", response_class=HTMLResponse)
async def renderizar_agenda(
    request: Request,
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Rota HTML: Renderiza a lista de consultas aplicando Autorização.
    - Recepcionistas/Admins veem a agenda global.
    - Médicos veem APENAS as próprias consultas (Mitigação BOLA).
    """
    # 1. Se for admin ou recepcionista, carrega a agenda global
    if current_user.get("role") in ["admin", "recepcionista"]:
        consultas_lista = session.exec(select(Consulta)).all()
    # 2. Se for médico, filtra (BOLA/Ownership) para mostrar apenas os seus pacientes
    elif current_user.get("role") == "medico":
        consultas_lista = session.exec(select(Consulta).where(Consulta.medico_id == current_user.get("sub"))).all()
    # 3. Bloqueia qualquer outro papel não mapeado
    else:
        raise HTTPException(status_code=403, detail="Acesso negado à agenda web.")

    return templates.TemplateResponse(
        request=request,
        name="agenda.html",
        context={"consultas": consultas_lista}
    )

# EXERCÍCIO 7: Endpoint Dedicado de Horários (M2M) - Acesso mínimo
@router.get("/vagas-laboratorio")
async def listar_vagas_laboratorio(
    current_user: dict = Security(get_current_user_with_scopes, scopes=["appointments:read"]),
    session: Session = Depends(get_session)
):
    """Retorna horários disponíveis omitindo dados sensíveis (PHI) via Egress Filtering estrito."""
    consultas = session.exec(select(Consulta).where(Consulta.status.in_(["agendada", "disponivel"]))).all()
    return [
        {
            "id": c.id,
            "data_hora": c.data_hora,
            "especialidade": c.especialidade,
            "medico_nome": c.medico_nome
        }
        for c in consultas
    ]


# EXERCÍCIO 9: VALIDAÇÃO WHITELIST E REGEX CONTRA SQL INJECTION / INPUT MALICIOSO
@router.get("/busca", response_model=List[ConsultaResponse])
async def buscar_consultas(
    termo: str = Query(...),
    current_user: dict = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """Rota de busca com validação ativa para evitar injeções, filtrada pelo escopo do usuário."""
    # Whitelist via Regex: Apenas letras, números e espaços são permitidos.
    if not re.match(r"^[a-zA-Z0-9\s]+$", termo):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Termo de busca inválido. Apenas caracteres alfanuméricos e espaços são permitidos."
        )

    statement = select(Consulta).where(Consulta.paciente_nome.contains(termo))

    # Aplicação do filtro de Ownership (BOLA)
    if current_user.get("role") == "medico":
        statement = statement.where(Consulta.medico_id == current_user.get("sub"))
    elif current_user.get("role") not in ["admin", "recepcionista"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado à busca de consultas."
        )

    return session.exec(statement).all()

# CÓDIGO ANTERIOR (EVIDÊNCIA EXERCÍCIO 8)
#@router.get("/{id}", response_model=ConsultaResponse)
#async def obter_consulta_vulneravel(
#    id: int = Path(...),
#    current_user: dict = Depends(get_current_user)
#):
#    consulta = consultas_db.get(id)
#    if not consulta:
#        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
#    # VULNERABILIDADE: Retorna a consulta sem checar o "ownership"
#    return consulta

@router.get("/{id}", response_model=ConsultaResponse)
async def obter_consulta(consulta: dict = Depends(get_owned_consulta)):
    # A verificação BOLA ocorre dinamicamente na injeção da dependência
    return consulta

# ==============================================================================
# CÓDIGO ANTERIOR (EVIDÊNCIA EXERCÍCIO 8 - ROTA LEGADA VULNERÁVEL)
# Ameaça mitigada: Zombie API / Improper Inventory Management (OWASP API9:2023)
# Motivo da remoção: A rota legada permitia bypass das defesas BOLA e BOPLA,
# pois aceitava requisições sem o Security Gate e sem o ConfigDict(extra='forbid').
# ==============================================================================
# @router.post("/legado", response_model=ConsultaResponse, status_code=status.HTTP_201_CREATED)
# async def criar_consulta_legado(consulta: ConsultaCreate):
#    """Cadastra uma nova consulta."""
#    novo_id = max(consultas_db.keys()) + 1 if consultas_db else 1
#    nova_consulta = consulta.model_dump()
#    nova_consulta["id"] = novo_id
#    nova_consulta["anotacoes_internas"] = "Agendamento criado via API web."
#    consultas_db[novo_id] = nova_consulta
#    return nova_consulta

# EXERCÍCIO 7: Defesa de Escopo M2M (Bloqueio de injeção externa)
@router.post("/", response_model=ConsultaResponse, status_code=status.HTTP_201_CREATED)
async def criar_consulta(
    consulta: ConsultaCreate,
    current_user: dict = Security(get_current_user_with_scopes, scopes=["appointments:write"]),
    session: Session = Depends(get_session)
):
    nova_consulta = Consulta(**consulta.model_dump())
    nova_consulta.anotacoes_internas = "Agendamento via API web."
    nova_consulta.medico_id = current_user.get("sub")

    session.add(nova_consulta)
    session.commit()
    session.refresh(nova_consulta)
    return nova_consulta


# CÓDIGO ANTERIOR (EVIDÊNCIA EXERCÍCIO 8)
# @router.put("/{id}", response_model=ConsultaResponse)
# async def editar_consulta(
#        consulta_in: ConsultaCreate,
#        id: int = Path(..., gt=0),
#        current_user: dict = Security(get_current_user_with_scopes, scopes=["appointments:write"])
# ):
#    consulta = consultas_db.get(id)
#    if not consulta:
#        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")
#    if current_user.get("role") == "medico" and consulta.get("medico_id") != current_user.get("sub"):
#        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")
#    atualizada = consulta_in.model_dump()
#    atualizada["id"] = id
#    atualizada["anotacoes_internas"] = consulta["anotacoes_internas"]
#    atualizada["medico_id"] = consulta["medico_id"]
#    consultas_db[id] = atualizada
#    return atualizada

@router.put("/{id}", response_model=ConsultaResponse)
async def editar_consulta(
        consulta_in: ConsultaCreate,
        id: int = Path(..., gt=0),
        consulta_bd: Consulta = Depends(get_owned_consulta),
        current_user: dict = Security(get_current_user_with_scopes, scopes=["appointments:write"]),
        session: Session = Depends(get_session)
):
    consulta_bd.paciente_nome = consulta_in.paciente_nome
    consulta_bd.medico_nome = consulta_in.medico_nome
    consulta_bd.data_hora = consulta_in.data_hora
    consulta_bd.especialidade = consulta_in.especialidade
    consulta_bd.status = consulta_in.status

    session.add(consulta_bd)
    session.commit()
    session.refresh(consulta_bd)
    return consulta_bd


# CÓDIGO ANTERIOR (EVIDÊNCIA EXERCÍCIO 8)
# @router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
# async def excluir_consulta(
#        id: int = Path(..., gt=0),
#        current_user: dict = Security(get_current_user_with_scopes, scopes=["appointments:write"])
# ):
#    consulta = consultas_db.get(id)
#    if not consulta:
#        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")
#    if current_user.get("role") == "medico" and consulta.get("medico_id") != current_user.get("sub"):
#        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")
#    del consultas_db[id]
#    return None

@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_consulta(
    id: int = Path(..., gt=0),
    consulta_bd: Consulta = Depends(get_owned_consulta),
    current_user: dict = Security(get_current_user_with_scopes, scopes=["appointments:write"]),
    session: Session = Depends(get_session)
):
    session.delete(consulta_bd)
    session.commit()
    return None