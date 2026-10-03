# Módulo dedicado à camada de persistência de dados (mock)

# Dicionário em memória que simula nosso banco de dados.
# Incluímos o campo "anotacoes_internas" para simular um dado sensível
# que não deve ser exposto publicamente na API (Egress Filtering).
consultas_db: dict[int, dict] = {
    1: {
        "id": 1,
        "paciente_nome": "Carlos Silva",
        "medico_nome": "Dr. Roberto",
        "medico_id": "11111111-1111-1111-1111-111111111111",
        "data_hora": "2026-10-15T10:00:00",
        "especialidade": "Cardiologia",
        "status": "agendada",
        "anotacoes_internas": "Paciente com histórico de arritmia na família."
    },
    2: {
        "id": 2,
        "paciente_nome": "Marina Souza",
        "medico_nome": "Dra. Ana",
        "medico_id": "22222222-2222-2222-2222-222222222222",
        "data_hora": "2026-10-16T14:30:00",
        "especialidade": "Dermatologia",
        "status": "concluida",
        "anotacoes_internas": "Primeira consulta clínica."
    },
    3: {
        "id": 3,
        "paciente_nome": "<script>alert('Fui hackeado')</script>",
        "medico_nome": "Dra. Teste",
        "medico_id": "99999999-9999-9999-9999-999999999999",
        "data_hora": "2026-10-15T10:00:00",
        "especialidade": "Teste",
        "status": "agendada",
        "anotacoes_internas": "DADO_SENSIVEL_NUNCA_VAZAR"
    }
}