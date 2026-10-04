from typing import Optional
from sqlmodel import SQLModel, Field as SQLModelField
from pydantic import BaseModel, Field as PydanticField, ConfigDict

# ==============================================================
# MODELO ORM (Entidade do Banco de Dados)
# ==============================================================
class Consulta(SQLModel, table=True):
    id: Optional[int] = SQLModelField(default=None, primary_key=True)
    paciente_nome: str
    medico_nome: str
    medico_id: str
    data_hora: str
    especialidade: str
    status: str
    anotacoes_internas: Optional[str] = SQLModelField(default=None)


# ==============================================================
# DTOs / SCHEMAS PYDANTIC (Proteção de Ingress/Egress)
# ==============================================================
class ConsultaCreate(BaseModel):
    """
    Modelo de Ingress (Entrada). Garante prevenção a BOPLA.
    """
    model_config = ConfigDict(extra='forbid')

    paciente_nome: str = PydanticField(..., min_length=2, max_length=100)
    medico_nome: str = PydanticField(..., min_length=2, max_length=100)
    data_hora: str = PydanticField(..., min_length=16, max_length=25)
    especialidade: str = PydanticField(..., min_length=2, max_length=50)
    status: str = PydanticField(..., min_length=2, max_length=20)


class ConsultaResponse(BaseModel):
    """
    Modelo de Egress (Saída).
    Omite anotacoes_internas prevenindo Information Disclosure.
    """
    model_config = ConfigDict(from_attributes=True)

    id: int
    paciente_nome: str
    medico_nome: str
    data_hora: str
    especialidade: str
    status: str

'''
==== CÓDIGO ANTERIOR (EVIDÊNCIA EXERCÍCIO 11 - Antes do SQLModel) ====

class ConsultaBase(BaseModel):
    """Modelo base descrevendo a entidade de Consulta."""
    id: int
    paciente_nome: str
    medico_nome: str
    data_hora: str
    especialidade: str
    status: str

# CÓDIGO ANTERIOR (EVIDÊNCIA EXERCÍCIO 8)
#class ConsultaCreate(BaseModel):
#    """
#    Modelo de Ingress (Entrada).
#    Garante que apenas os dados definidos sejam aceitos e validados.
#    """
#    # VULNERABILIDADE: O modelo aceita e confia em campos de controle do sistema
#    paciente_nome: str = Field(..., min_length=2, max_length=100)
#    medico_nome: str = Field(..., min_length=2, max_length=100)
#    data_hora: str = Field(..., min_length=16, max_length=25)
#    especialidade: str = Field(..., min_length=2, max_length=50)
#    status: str = Field(..., min_length=2, max_length=20) # Campo crítico de estado liberado para o input do usuário
#    # Ausência de bloqueio para campos não mapeados (extra='forbid')

class ConsultaCreate(BaseModel):
   """
   Modelo de Ingress (Entrada).
   Garante que apenas os dados definidos sejam aceitos e validados.
   """
   # EXERCÍCIO 9 - PROTEÇÃO CONTRA BOPLA / MASS ASSIGNMENT
   model_config = ConfigDict(extra='forbid')

   paciente_nome: str = Field(..., min_length=2, max_length=100)
   medico_nome: str = Field(..., min_length=2, max_length=100)
   data_hora: str = Field(..., min_length=16, max_length=25)
   especialidade: str = Field(..., min_length=2, max_length=50)
   status: str = Field(..., min_length=2, max_length=20)

class ConsultaResponse(BaseModel):
    """
    Modelo de Egress (Saída).
    Filtra a resposta para expor apenas os campos seguros, omitindo IDs
    internos não mapeados e campos sensíveis do banco de dados.
    """
    id: int
    paciente_nome: str
    medico_nome: str
    data_hora: str
    especialidade: str
    status: str
'''