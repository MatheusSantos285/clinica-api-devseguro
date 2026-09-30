from fastapi.testclient import TestClient
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