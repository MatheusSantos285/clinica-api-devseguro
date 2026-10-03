import re
from fastapi import APIRouter, HTTPException, status, Path, Request, Depends, Security, Query
from fastapi.responses import HTMLResponse
from typing import List
from fastapi.templating import Jinja2Templates
from models.consultas import ConsultaCreate, ConsultaResponse
from database.consultas import consultas_db
from auth.authenticate import get_current_user, get_current_user_with_scopes

# Concentra os controladores e a definição dos endpoints RESTful
router = APIRouter(prefix="/consultas", tags=["Consultas"])
# Configuração do Jinja2 apontando para o diretório de templates
templates = Jinja2Templates(directory="templates")

# EXERCÍCIO 9 - DEPENDÊNCIA CENTRALIZADA CONTRA BOLA (IDOR)
def get_owned_consulta(id: int = Path(...), current_user: dict = Depends(get_current_user)) -> dict:
    """
    Busca a consulta e verifica a propriedade (Ownership).
    Mitiga a enumeração de IDs devolvendo 404 em vez de 403.
    """
    consulta = consultas_db.get(id)
    if not consulta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")

    # Validação de ownership: Se for médico, só acessa os seus próprios pacientes.
    if current_user.get("role") == "medico" and consulta.get("medico_id") != current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")

    return consulta

# CÓDIGO ANTERIOR (EVIDÊNCIA EXERCÍCIO 8)
#@router.get("/", response_model=List[ConsultaResponse])
#async def listar_consultas():
#    """Retorna a lista de todas as consultas agendadas."""
#    return list(consultas_db.values())

@router.get("/", response_model=List[ConsultaResponse])
async def listar_consultas(current_user: dict = Depends(get_current_user)):
    """Retorna a lista de consultas filtrada com base no papel e propriedade do usuário."""

    # Se o usuário for um administrador, ele tem privilégios para ver a agenda global
    if current_user.get("role") == "admin":
        return list(consultas_db.values())

    # Se for um médico, filtramos a lista devolvendo APENAS as consultas dele
    elif current_user.get("role") == "medico":
        consultas_do_medico = [
            c for c in consultas_db.values()
            if c.get("medico_id") == current_user.get("sub")
        ]
        return consultas_do_medico

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
    current_user: dict = Depends(get_current_user)
):
    """
    Rota HTML: Renderiza a lista de consultas aplicando Autorização.
    - Recepcionistas/Admins veem a agenda global.
    - Médicos veem APENAS as próprias consultas (Mitigação BOLA).
    """
    # 1. Se for admin ou recepcionista, carrega a agenda global
    if current_user.get("role") in ["admin", "recepcionista"]:
        consultas_lista = list(consultas_db.values())

    # 2. Se for médico, filtra (BOLA/Ownership) para mostrar apenas os seus pacientes
    elif current_user.get("role") == "medico":
        consultas_lista = [
            c for c in consultas_db.values()
            if c.get("medico_id") == current_user.get("sub")
        ]

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
    current_user: dict = Security(get_current_user_with_scopes, scopes=["appointments:read"])
):
    """Retorna horários disponíveis omitindo dados sensíveis (PHI) via Egress Filtering estrito."""
    vagas = []
    for consulta in consultas_db.values():
        if consulta.get("status") in ["agendada", "disponivel"]:
            vagas.append({
                "id": consulta["id"],
                "data_hora": consulta["data_hora"],
                "especialidade": consulta["especialidade"],
                "medico_nome": consulta["medico_nome"]
            })
    return vagas


# EXERCÍCIO 9: VALIDAÇÃO WHITELIST E REGEX CONTRA SQL INJECTION / INPUT MALICIOSO
@router.get("/busca", response_model=List[ConsultaResponse])
async def buscar_consultas(
        termo: str = Query(...),
        current_user: dict = Depends(get_current_user)  # <- Injeção de Segurança adicionada
):
    """Rota de busca com validação ativa para evitar injeções, filtrada pelo escopo do usuário."""
    # Whitelist via Regex: Apenas letras, números e espaços são permitidos.
    if not re.match(r"^[a-zA-Z0-9\s]+$", termo):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Termo de busca inválido. Apenas caracteres alfanuméricos e espaços são permitidos."
        )

    # Lógica base de busca
    resultados = [
        c for c in consultas_db.values()
        if termo.lower() in c.get("paciente_nome", "").lower()
    ]

    # Aplicação do filtro de Ownership (BOLA)
    if current_user.get("role") == "medico":
        resultados = [
            c for c in resultados
            if c.get("medico_id") == current_user.get("sub")
        ]
    elif current_user.get("role") not in ["admin", "recepcionista"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso negado à busca de consultas."
        )

    return resultados

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
    current_user: dict = Security(get_current_user_with_scopes, scopes=["appointments:write"])
):
    novo_id = max(consultas_db.keys()) + 1 if consultas_db else 1
    nova_consulta = consulta.model_dump()
    nova_consulta["id"] = novo_id
    nova_consulta["anotacoes_internas"] = "Agendamento via API web."
    nova_consulta["medico_id"] = current_user.get("sub")
    consultas_db[novo_id] = nova_consulta
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
       consulta: dict = Depends(get_owned_consulta),  # Injeção para BOLA
       current_user: dict = Security(get_current_user_with_scopes, scopes=["appointments:write"])
):
   atualizada = consulta_in.model_dump()
   atualizada["id"] = id
   atualizada["anotacoes_internas"] = consulta["anotacoes_internas"]
   atualizada["medico_id"] = consulta["medico_id"]
   consultas_db[id] = atualizada
   return atualizada


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

# EXERCÍCIO 9: RESOLUÇÃO DA VULNERABILIDADE IDENTIFICADA NA ROTA DELETE
@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_consulta(
       id: int = Path(..., gt=0),
       consulta: dict = Depends(get_owned_consulta),  # Injeção para BOLA
       current_user: dict = Security(get_current_user_with_scopes, scopes=["appointments:write"])
):
   del consultas_db[id]
   return None