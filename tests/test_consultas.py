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

def test_bloqueio_usuario_nao_admin_em_rota_restrita_admin():
    """Garante que um médico sem papel 'admin' seja bloqueado pela rota restrita BFLA."""

    # 1. Simula login de um médico
    login_response = client.post(
        "/user/login",
        data={"username": "medico_a@clinica.com", "password": "senha123"}
    )
    assert login_response.status_code == 200
    token = login_response.json()["access_token"]

    # 2. Tenta acessar rota restrita de admin com o token emitido
    response = client.get(
        "/admin/dashboard",
        headers={"Authorization": f"Bearer {token}"}
    )

    # 3. Validações
    assert response.status_code == 403
    assert response.json()["detail"] == "Acesso restrito a Administradores do sistema (BFLA Block)."


def test_autenticacao_m2m_laboratorio_sucesso():
    """Valida a emissão do token M2M Client Credentials e o sucesso no consumo da rota permitida."""
    # 1. Autenticação Client Credentials
    response_auth = client.post(
        "/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "lab_parceiro_01",
            "client_secret": "LabSecret#2026"
        }
    )
    assert response_auth.status_code == 200
    token = response_auth.json()["access_token"]

    # 2. Acesso Autorizado
    response_vagas = client.get(
        "/consultas/vagas-laboratorio",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response_vagas.status_code == 200
    vagas = response_vagas.json()
    assert isinstance(vagas, list)

    # Egress Filtering (ausência de dados de pacientes)
    if len(vagas) > 0:
        assert "paciente_nome" not in vagas[0]
        assert "anotacoes_internas" not in vagas[0]


def test_bloqueio_escopo_m2m_tentando_acao_nao_autorizada():
    """Valida o isolamento de escopos e menor privilégio bloqueando tentativas de escrita (403)."""
    # 1. Emissão de Token com menor privilégio (appointments:read)
    response_auth = client.post(
        "/oauth/token",
        data={
            "grant_type": "client_credentials",
            "client_id": "lab_parceiro_01",
            "client_secret": "LabSecret#2026"
        }
    )
    token = response_auth.json()["access_token"]

    # 2. Acesso Negado em rota de escrita (appointments:write)
    response_post = client.post(
        "/consultas/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "paciente_nome": "Injeção M2M",
            "medico_nome": "Dr. Hacker",
            "data_hora": "2026-12-31T23:59:00",
            "especialidade": "Exploitation",
            "status": "agendada"
        }
    )

    # 3. Asserções
    assert response_post.status_code == 403
    assert response_post.json()["detail"] == "Permissão insuficiente: escopos ausentes no token"