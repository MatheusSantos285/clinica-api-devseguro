from fastapi import APIRouter, HTTPException, status, Path, Request, Depends, Security
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

@router.get("/", response_model=List[ConsultaResponse])
async def listar_consultas():
    """Retorna a lista de todas as consultas agendadas."""
    return list(consultas_db.values())

@router.get("/agenda-html", response_class=HTMLResponse)
async def renderizar_agenda(request: Request):
    """
    Rota HTML: Renderiza a lista de consultas para a recepção,
    utilizando Jinja2 e garantindo o mascaramento do campo interno.
    """
    consultas_lista = list(consultas_db.values())
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

@router.get("/{id}", response_model=ConsultaResponse)
async def obter_consulta(
        id: int = Path(..., gt=0, description="Identificador único da consulta")
):
    """
    Busca uma consulta específica pelo ID. O parâmetro Path atua como
    validador numérico (gt=0).
    """
    consulta = consultas_db.get(id)
    if not consulta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Consulta não encontrada."
        )
    return consulta

@router.post("/legado", response_model=ConsultaResponse, status_code=status.HTTP_201_CREATED)
async def criar_consulta(consulta: ConsultaCreate):
    """Cadastra uma nova consulta."""
    novo_id = max(consultas_db.keys()) + 1 if consultas_db else 1

    # Utilizamos model_dump() para serializar a entrada
    nova_consulta = consulta.model_dump()
    nova_consulta["id"] = novo_id

    # Campo sensível criado pelo sistema que o Response_Model vai ocultar
    nova_consulta["anotacoes_internas"] = "Agendamento criado via API web."

    consultas_db[novo_id] = nova_consulta
    return nova_consulta

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


@router.put("/{id}", response_model=ConsultaResponse)
async def editar_consulta(
        consulta_in: ConsultaCreate,
        id: int = Path(..., gt=0),
        current_user: dict = Security(get_current_user_with_scopes, scopes=["appointments:write"])
):
    consulta = consultas_db.get(id)
    if not consulta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")

    if current_user.get("role") == "medico" and consulta.get("medico_id") != current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")

    atualizada = consulta_in.model_dump()
    atualizada["id"] = id
    atualizada["anotacoes_internas"] = consulta["anotacoes_internas"]
    atualizada["medico_id"] = consulta["medico_id"]
    consultas_db[id] = atualizada
    return atualizada


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def excluir_consulta(
        id: int = Path(..., gt=0),
        current_user: dict = Security(get_current_user_with_scopes, scopes=["appointments:write"])
):
    consulta = consultas_db.get(id)
    if not consulta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")

    if current_user.get("role") == "medico" and consulta.get("medico_id") != current_user.get("sub"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta não encontrada.")

    del consultas_db[id]
    return None