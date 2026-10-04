import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from main import app
from database.connection import get_session
from models.users import User
from models.consultas import Consulta
from auth.hash_password import HashPassword
from config.rate_limiter import limiter

# 1. Configurando Banco de Dados em Memória Temporário para Isolamento
sqlite_url = "sqlite:///:memory:"
engine_test = create_engine(
    sqlite_url,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool # Mantém 1 única conexão viva compartilhando os mesmos dados
)

def override_get_session():
    with Session(engine_test) as session:
        yield session

# Sobrescreve a dependência em tempo de execução
app.dependency_overrides[get_session] = override_get_session
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_teardown_test_environment():
    """Garante ambiente de DB zerado e Rate Limits limpos a cada novo teste."""
    limiter._storage.reset()
    SQLModel.metadata.drop_all(engine_test)
    SQLModel.metadata.create_all(engine_test)

    with Session(engine_test) as session:
        # Seeding inicial mínimo para execução dos testes
        session.add_all([
            User(id="33333333", email="recepcionista@clinica.com",
                 hashed_password=HashPassword.hash_password("senha123"), role="recepcionista"),
            User(id="11111111-1111-1111-1111-111111111111", email="medico_a@clinica.com",
                 hashed_password=HashPassword.hash_password("senha123"), role="medico"),
            User(id="22222222-2222-2222-2222-222222222222", email="medico_b@clinica.com",
                 hashed_password=HashPassword.hash_password("senha123"), role="medico"),
            User(id="lab_parceiro_01", hashed_password=HashPassword.hash_password("LabSecret#2026"), role="m2m",
                 scopes="appointments:read", is_m2m=True)
        ])

        session.add_all([
            Consulta(id=1, paciente_nome="Carlos Silva", medico_nome="Dr. Roberto",
                     medico_id="11111111-1111-1111-1111-111111111111", data_hora="2026-10-15T10:00:00",
                     especialidade="Cardiologia", status="agendada", anotacoes_internas="Histórico interno"),
        ])
        session.commit()


def get_auth_token(username="medico_a@clinica.com", password="senha123"):
    """Função auxiliar para reduzir a repetição de código (DRY) na geração de tokens."""
    response = client.post("/user/login", data={"username": username, "password": password})
    return response.json()["access_token"]


def test_listar_consultas_sucesso():
    token = get_auth_token()
    response = client.get("/consultas/", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    dados = response.json()
    assert isinstance(dados, list)
    assert len(dados) >= 1


def test_obter_consulta_por_id_sucesso():
    token = get_auth_token()
    response = client.get("/consultas/1", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    dados = response.json()
    assert isinstance(dados, dict)


def test_obter_consulta_por_id_falha():
    token = get_auth_token()
    response = client.get("/consultas/2", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404


def test_garantir_nao_vazamento_anotacoes_internas_json():
    token = get_auth_token()
    response = client.get("/consultas/1", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    dados = response.json()
    assert "anotacoes_internas" not in dados


def test_renderizacao_agenda_html_sucesso_e_seguranca_recepcionista():
    """
    Valida renderização HTML, respeito à LGPD e mitigação de XSS através
    da checagem do auto-escape do motor Jinja2.
    """
    # 1. Setup: Injetamos um payload XSS e um dado restrito diretamente no Banco de Dados via ORM
    with Session(engine_test) as session:
        consulta_maliciosa = Consulta(
            id=999,
            paciente_nome="<script>alert('Fui hackeado')</script>",
            medico_nome="Dra. Teste",
            medico_id="99999999-9999-9999-9999-999999999999",
            data_hora="2026-10-15T10:00:00",
            especialidade="Teste",
            status="agendada",
            anotacoes_internas="DADO_SENSIVEL_NUNCA_VAZAR"
        )
        session.add(consulta_maliciosa)
        session.commit()

    token = get_auth_token(username="recepcionista@clinica.com")

    # 2. Execução da rota HTML
    response = client.get("/consultas/agenda-html", headers={"Authorization": f"Bearer {token}"})
    html_content = response.text

    # 3. Asserções de Sucesso e de Segurança
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "DADO_SENSIVEL_NUNCA_VAZAR" not in html_content
    assert "<script>alert('Fui hackeado')</script>" not in html_content
    assert "&lt;script&gt;" in html_content or "&#39;" in html_content


def test_renderizacao_agenda_html_sucesso_e_seguranca_medico():
    """
    Valida renderização HTML e a aplicação correta da mitigação de BOLA
    para um perfil de médico. O médico só deve enxergar as suas consultas.
    """
    # 1. Setup: Injetamos uma consulta maliciosa que NÃO pertence ao Médico A via ORM
    with Session(engine_test) as session:
        consulta_terceiro = Consulta(
            id=999,
            paciente_nome="<script>alert('Fui hackeado')</script>",
            medico_nome="Dra. Teste",
            medico_id="99999999-9999-9999-9999-999999999999",  # <- Dono diferente do Médico A
            data_hora="2026-10-15T10:00:00",
            especialidade="Teste",
            status="agendada",
            anotacoes_internas="DADO_SENSIVEL_NUNCA_VAZAR"
        )
        session.add(consulta_terceiro)
        session.commit()

    token = get_auth_token(username="medico_a@clinica.com")

    # 2. Execução da rota HTML
    response = client.get("/consultas/agenda-html", headers={"Authorization": f"Bearer {token}"})
    html_content = response.text

    # 3. Asserções de Sucesso e de Segurança
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "DADO_SENSIVEL_NUNCA_VAZAR" not in html_content

    # Validação de BOLA: A consulta não deve aparecer em formato algum (nem cru, nem escapado)
    assert "<script>alert('Fui hackeado')</script>" not in html_content
    assert "&lt;script&gt;" not in html_content


def test_renderizacao_agenda_html_sem_token():
    response = client.get("/consultas/agenda-html")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


def test_bloqueio_usuario_nao_admin_em_rota_restrita_admin():
    token = get_auth_token(username="medico_a@clinica.com")
    response = client.get("/admin/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403
    assert response.json()["detail"] == "Acesso restrito a Administradores do sistema (BFLA Block)."


def test_autenticacao_m2m_laboratorio_sucesso():
    response_auth = client.post(
        "/oauth/token",
        data={"grant_type": "client_credentials", "client_id": "lab_parceiro_01", "client_secret": "LabSecret#2026"}
    )
    assert response_auth.status_code == 200
    token = response_auth.json()["access_token"]

    response_vagas = client.get("/consultas/vagas-laboratorio", headers={"Authorization": f"Bearer {token}"})
    assert response_vagas.status_code == 200

    vagas = response_vagas.json()
    assert isinstance(vagas, list)
    if len(vagas) > 0:
        assert "paciente_nome" not in vagas[0]
        assert "anotacoes_internas" not in vagas[0]


def test_bloqueio_escopo_m2m_tentando_acao_nao_autorizada():
    response_auth = client.post(
        "/oauth/token",
        data={"grant_type": "client_credentials", "client_id": "lab_parceiro_01", "client_secret": "LabSecret#2026"}
    )
    token = response_auth.json()["access_token"]

    response_post = client.post(
        "/consultas/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "paciente_nome": "Injeção M2M", "medico_nome": "Dr. Hacker",
            "data_hora": "2026-12-31T23:59:00", "especialidade": "Exploitation", "status": "agendada"
        }
    )
    assert response_post.status_code == 403
    assert response_post.json()["detail"] == "Permissão insuficiente: escopos ausentes no token"


def test_defesa_bola_consulta_terceiros():
    token = get_auth_token(username="medico_b@clinica.com")
    response = client.get("/consultas/1", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Consulta não encontrada."


def test_defesa_bopla_campos_extras():
    token = get_auth_token()
    response = client.post(
        "/consultas/",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "paciente_nome": "Paciente Valido", "medico_nome": "Dr. Médico A",
            "data_hora": "2026-12-01T10:00:00", "especialidade": "Geral",
            "status": "agendada", "is_admin": True, "anotacoes_internas": "Tentando forçar input"
        }
    )
    assert response.status_code == 422


def test_defesa_regex_busca_maliciosa():
    token = get_auth_token()
    response = client.get("/consultas/busca?termo=' OR '1'='1", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 400
    assert "Termo de busca inválido" in response.json()["detail"]


def test_busca_valida_com_sucesso():
    token = get_auth_token()
    response = client.get("/consultas/busca?termo=Carlos Silva", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200


def test_defesa_bola_delecao_nao_autorizada():
    token = get_auth_token(username="medico_b@clinica.com")
    response = client.delete("/consultas/1", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Consulta não encontrada."


def test_validar_cors_origem_autorizada():
    response = client.get("/", headers={"Origin": "http://localhost:3000"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


def test_validar_presenca_security_headers():
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers.get("Strict-Transport-Security") == "max-age=31536000; includeSubDomains"
    assert response.headers.get("X-Frame-Options") == "DENY"
    assert response.headers.get("X-Content-Type-Options") == "nosniff"


def test_rate_limiting_estouro_login():
    ip_alvo = "203.0.113.10"
    for _ in range(5):
        res = client.post(
            "/user/login",
            data={"username": "medico_a@clinica.com", "password": "senha123"},
            headers={"X-Forwarded-For": ip_alvo}
        )
        assert res.status_code == 200

    res_bloqueada = client.post(
        "/user/login",
        data={"username": "medico_a@clinica.com", "password": "senha123"},
        headers={"X-Forwarded-For": ip_alvo}
    )
    assert res_bloqueada.status_code == 429
    assert "Rate limit exceeded" in res_bloqueada.json()["error"]