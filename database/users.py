from auth.hash_password import HashPassword

# Dicionário em memória que simula o banco de usuários
users_db = {
    "recepcionista@clinica.com": {
        "id": "33333333-3333-3333-3333-333333333333",
        "email": "recepcionista@clinica.com",
        "password": HashPassword.hash_password("senha123"),
        "role": "recepcionista"
    },
    "medico_a@clinica.com": {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "medico_a@clinica.com",
        "password": HashPassword.hash_password("senha123"),
        "role": "medico"
    },
    "medico_b@clinica.com": {
        "id": "22222222-2222-2222-2222-222222222222",
        "email": "medico_b@clinica.com",
        "password": HashPassword.hash_password("senha123"),
        "role": "medico"
    },
    "admin@clinica.com": {
        "id": "00000000-0000-0000-0000-000000000000",
        "email": "admin@clinica.com",
        "password": HashPassword.hash_password("senha123"),
        "role": "admin",
        "mfa_secret": "123456" # Fator extra para administradores
    }
}