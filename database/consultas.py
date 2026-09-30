# Módulo dedicado à camada de persistência de dados (mock)

# Dicionário em memória que simula nosso banco de dados.
# Incluímos o campo "anotacoes_internas" para simular um dado sensível
# que não deve ser exposto publicamente na API (Egress Filtering).
consultas_db: dict[int, dict] = {
    1: {
        "id": 1,
        "paciente_nome": "Carlos Silva",
        "medico_nome": "Dr. Roberto",
        "data_hora": "2026-10-15T10:00:00",
        "especialidade": "Cardiologia",
        "status": "agendada",
        "anotacoes_internas": "Paciente com histórico de arritmia na família."
    },
    2: {
        "id": 2,
        "paciente_nome": "Marina Souza",
        "medico_nome": "Dra. Ana",
        "data_hora": "2026-10-16T14:30:00",
        "especialidade": "Dermatologia",
        "status": "concluida",
        "anotacoes_internas": "Primeira consulta clínica."
    }
}