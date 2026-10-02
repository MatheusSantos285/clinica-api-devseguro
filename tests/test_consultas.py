from fastapi.testclient import TestClient

from database.consultas import consultas_db
from main import app

client = TestClient(app)

def test_listar_consultas_sucesso():
    response = client.get("/consultas/")
    assert response.status_code == 200
    dados = response.json()
    assert isinstance(dados, list)
    assert len(dados) >= 2

def test_obter_consulta_por_id_sucesso():
    response = client.get("/consultas/1")
    assert response.status_code == 200
    dados = response.json()
    assert dados["id"] == 1
    assert dados["paciente_nome"] == "Carlos Silva"
    # Garante que o Egress Filtering funcionou (campo interno não vazou)
    assert "anotacoes_internas" not in dados

def test_garantir_nao_vazamento_anotacoes_internas_json():
    """Garante que a API JSON aplique Egress Filtering."""
    response = client.get("/consultas/1")
    assert response.status_code == 200
    dados = response.json()
    assert "anotacoes_internas" not in dados


def test_renderizacao_agenda_html_sucesso_e_seguranca():
    """
    Valida renderização HTML, respeito à LGPD e mitigação de XSS através
    da checagem do auto-escape do motor Jinja2.
    """
    # 1. Setup: Injetamos um payload XSS e um dado restrito no banco
    consultas_db[999] = {
        "id": 999,
        "paciente_nome": "<script>alert('Fui hackeado')</script>",
        "medico_nome": "Dra. Teste",
        "data_hora": "2026-10-15T10:00:00",
        "especialidade": "Teste",
        "status": "agendada",
        "anotacoes_internas": "DADO_SENSIVEL_NUNCA_VAZAR"
    }

    # 2. Execução da rota HTML
    response = client.get("/consultas/agenda-html")
    html_content = response.text

    # 3. Asserções de Sucesso e de Segurança
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    # Valida LGPD: O dado sensível não pode constar na tela
    assert "DADO_SENSIVEL_NUNCA_VAZAR" not in html_content

    # Valida Segurança XSS: O payload precisa estar escapado (ex: &lt;script&gt;)
    assert "<script>alert('Fui hackeado')</script>" not in html_content
    assert "&lt;script&gt;" in html_content or "&#39;" in html_content

    # Teardown: Limpeza do banco mockado
    del consultas_db[999]