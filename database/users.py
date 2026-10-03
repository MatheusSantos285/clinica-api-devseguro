from auth.hash_password import HashPassword

# Dicionário em memória que simula o banco de usuários e clientes (IdP)
users_db = {
    "recepcionista@clinica.com": {
        "id": "33333333-3333-3333-3333-333333333333",
        "email": "recepcionista@clinica.com",
        "password": HashPassword.hash_password("senha123"),
        "role": "recepcionista",
        "type": "user"
    },
    "medico_a@clinica.com": {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "medico_a@clinica.com",
        "password": HashPassword.hash_password("senha123"),
        "role": "medico",
        "type": "user"
    },
    "medico_b@clinica.com": {
        "id": "22222222-2222-2222-2222-222222222222",
        "email": "medico_b@clinica.com",
        "password": HashPassword.hash_password("senha123"),
        "role": "medico",
        "type": "user"
    },
    "admin@clinica.com": {
        "id": "00000000-0000-0000-0000-000000000000",
        "email": "admin@clinica.com",
        "password": HashPassword.hash_password("senha123"),
        "role": "admin",
        "mfa_secret": "123456",
        "type": "user"
    },
    # EXERCÍCIO 7: Cadastro do Cliente M2M (Laboratório Parceiro)
    "lab_parceiro_01": {
        "id": "lab_parceiro_01",
        "password": HashPassword.hash_password("LabSecret#2026"), # Atua como client_secret
        "scopes": ["appointments:read"],
        "type": "m2m",
        "role": "m2m"
    }
}