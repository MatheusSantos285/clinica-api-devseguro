from fastapi import APIRouter, HTTPException, status, Path, Request
from fastapi.responses import HTMLResponse
from typing import List
from fastapi.templating import Jinja2Templates
from models.consultas import ConsultaCreate, ConsultaResponse
from database.consultas import consultas_db

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


@router.post("/", response_model=ConsultaResponse, status_code=status.HTTP_201_CREATED)
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