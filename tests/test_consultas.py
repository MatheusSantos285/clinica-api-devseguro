import pytest
from fastapi.testclient import TestClient
from config.rate_limiter import limiter
from database.consultas import consultas_db
from main import app

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_rate_limits():
    """
    Limpa o histórico de requisições na memória do SlowAPI antes de cada teste.
    Isso garante que um teste não consuma a cota de Rate Limiting do outro.
    """
    limiter._storage.reset()

def test_listar_consultas_sucesso():
    login_response = client.post(
        "/user/login",
        data={"username": "medico_a@clinica.com", "password": "senha123"}
    )
    token = login_response.json()["access_token"]
    response = client.get("/consultas/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    dados = response.json()
    assert isinstance(dados, list)
    assert len(dados) >= 1

def test_obter_consulta_por_id_sucesso():
    login_response = client.post(
        "/user/login",
        data={"username": "medico_a@clinica.com", "password": "senha123"}
    )
    token = login_response.json()["access_token"]
    response = client.get("/consultas/1", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    dados = response.json()
    assert isinstance(dados, dict)

def test_obter_consulta_por_id_falha():
    login_response = client.post(
        "/user/login",
        data={"username": "medico_a@clinica.com", "password": "senha123"}
    )
    token = login_response.json()["access_token"]
    response = client.get("/consultas/2", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404

def test_garantir_nao_vazamento_anotacoes_internas_json():
   # Precisamos gerar token pois a rota get_owned_consulta agora exige
   login_response = client.post(
       "/user/login",
       data={"username": "medico_a@clinica.com", "password": "senha123"}
   )
   token = login_response.json()["access_token"]
   response = client.get("/consultas/1", headers={"Authorization": f"Bearer {token}"})
   assert response.status_code == 200
   dados = response.json()
   assert "anotacoes_internas" not in dados

def test_renderizacao_agenda_html_sucesso_e_seguranca_recepcionista():
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

    login_response = client.post(
        "/user/login",
        data={"username": "recepcionista@clinica.com", "password": "senha123"}
    )
    token = login_response.json()["access_token"]
    # 2. Execução da rota HTML
    response = client.get("/consultas/agenda-html", headers={"Authorization": f"Bearer {token}"})
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


def test_renderizacao_agenda_html_sucesso_e_seguranca_medico():
    """
    Valida renderização HTML e a aplicação correta da mitigação de BOLA
    para um perfil de médico. O médico só deve enxergar as suas consultas.
    """
    # 1. Setup: Injetamos uma consulta maliciosa que NÃO pertence ao Médico A
    consultas_db[999] = {
        "id": 999,
        "paciente_nome": "<script>alert('Fui hackeado')</script>",
        "medico_nome": "Dra. Teste",  # <- Dono diferente do Médico A
        "medico_id": "99999999-9999-9999-9999-999999999999",
        "data_hora": "2026-10-15T10:00:00",
        "especialidade": "Teste",
        "status": "agendada",
        "anotacoes_internas": "DADO_SENSIVEL_NUNCA_VAZAR"
    }

    # Autentica como Médico A
    login_response = client.post(
        "/user/login",
        data={"username": "medico_a@clinica.com", "password": "senha123"}
    )
    token = login_response.json()["access_token"]

    # 2. Execução da rota HTML
    response = client.get("/consultas/agenda-html", headers={"Authorization": f"Bearer {token}"})
    html_content = response.text

    # 3. Asserções de Sucesso e de Segurança
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

    # Validação LGPD / Egress Filtering: O dado sensível não pode constar na tela
    assert "DADO_SENSIVEL_NUNCA_VAZAR" not in html_content

    # VALIDAÇÃO DE BOLA: O médico NÃO pode ver o payload do paciente da Dra. Teste
    # Nem cru, nem escapado. A consulta inteira deve ser suprimida da view.
    assert "<script>alert('Fui hackeado')</script>" not in html_content
    assert "&lt;script&gt;" not in html_content

    # Teardown: Limpeza do banco mockado
    del consultas_db[999]

def test_renderizacao_agenda_html_sem_token():
    """Garante que a rota HTML de agenda não seja acessível sem token."""
    response = client.get("/consultas/agenda-html")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"

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

# ===== Exercicio 9 ======
def test_defesa_bola_consulta_terceiros():
    """Asserta que um médico acessando a consulta de outro recebe HTTP 404 Not Found."""
    login_response = client.post(
        "/user/login",
        data={"username": "medico_b@clinica.com", "password": "senha123"}
    )
    token = login_response.json()["access_token"]

    # Médico B tenta acessar a consulta ID 1 (Que pertence ao Médico A)
    response = client.get(
        "/consultas/1",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Consulta não encontrada."


def test_defesa_bopla_campos_extras():
    """Asserta que enviar JSON com campo extra retorna HTTP 422 Unprocessable Content."""
    login_response = client.post(
        "/user/login",
        data={"username": "medico_a@clinica.com", "password": "senha123"}
    )
    token = login_response.json()["access_token"]

    response = client.post(
        "/consultas/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "paciente_nome": "Paciente Valido",
            "medico_nome": "Dr. Médico A",
            "data_hora": "2026-12-01T10:00:00",
            "especialidade": "Geral",
            "status": "agendada",
            "is_admin": True,  # Campo não suportado (Mass Assignment)
            "anotacoes_internas": "Tentando forçar input restrito"
        }
    )
    assert response.status_code == 422


def test_defesa_regex_busca_maliciosa():
    """Asserta que enviar termo malicioso retorna 400 Bad Request mesmo autenticado."""
    # Gera o Token
    login_response = client.post(
        "/user/login",
        data={"username": "medico_a@clinica.com", "password": "senha123"}
    )
    token = login_response.json()["access_token"]

    # Realiza a chamada enviando o Token
    response = client.get(
        "/consultas/busca?termo=' OR '1'='1",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 400
    assert "Termo de busca inválido" in response.json()["detail"]


def test_busca_valida_com_sucesso():
    """Valida o funcionamento correto da busca quando o usuário está autenticado e o termo é válido."""
    login_response = client.post(
        "/user/login",
        data={"username": "medico_a@clinica.com", "password": "senha123"}
    )
    token = login_response.json()["access_token"]

    response = client.get(
        "/consultas/busca?termo=Carlos Silva",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200


def test_defesa_bola_delecao_nao_autorizada():
    """Asserta que tentar deletar consulta de outro médico retorna HTTP 404 Not Found."""
    login_response = client.post(
        "/user/login",
        data={"username": "medico_b@clinica.com", "password": "senha123"}
    )
    token = login_response.json()["access_token"]

    # Médico B tenta excluir a consulta ID 1 (Que pertence ao Médico A)
    response = client.delete(
        "/consultas/1",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Consulta não encontrada."

def test_validar_cors_origem_autorizada():
    """Valida a presença do Header CORS ao enviar uma requisição de Origem permitida."""
    response = client.get("/", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"

def test_validar_presenca_security_headers():
    """Valida que o middleware global injeta corretamente os headers de segurança HSTS e Anti-Clickjacking."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"

def test_rate_limiting_estouro_login():
    """
    Testa o limite estrito de 5 requests/minuto no endpoint de Login.
    Enviamos um IP 'falso' para não afetar o rate limit de outros testes no TestClient.
    """
    ip_alvo = "203.0.113.10"

    # Consumir a cota das 5 requisições iniciais
    for _ in range(5):
        res = client.post(
            "/user/login",
            data={"username": "medico_a@clinica.com", "password": "senha123"},
            headers={"X-Forwarded-For": ip_alvo}
        )
        assert res.status_code == 200

    # 6ª Requisição: Acesso Negado pelo Rate Limiter
    res_bloqueada = client.post(
        "/user/login",
        data={"username": "medico_a@clinica.com", "password": "senha123"},
        headers={"X-Forwarded-For": ip_alvo}
    )
    assert res_bloqueada.status_code == 429
    assert "Rate limit exceeded" in res_bloqueada.json()["error"]