from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlmodel import Session, select

from config.rate_limiter import limiter
from routes.consultas import router as consultas_router
from routes.admin import router as admin_router
from routes.user import router as user_router
from database.connection import create_db_and_tables, engine
from models.users import User
from models.consultas import Consulta
from auth.hash_password import HashPassword

app = FastAPI(title="Clínica Médica - API de Agendamento (Database Ready)")

# Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS Allowlist
origins = ["http://localhost:3000", "http://127.0.0.1:3000", "https://parceiro-autorizado.com"]
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"], allow_headers=["*"],
)


# Security Headers HTTP
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


# Seeding de Usuários e Consultas Iniciais Mockadas
def populate_db():
    with Session(engine) as session:
        if not session.exec(select(User)).first():
            users_mock = [
                User(id="33333333-3333-3333-3333-333333333333", email="recepcionista@clinica.com",
                     hashed_password=HashPassword.hash_password("senha123"), role="recepcionista"),
                User(id="11111111-1111-1111-1111-111111111111", email="medico_a@clinica.com",
                     hashed_password=HashPassword.hash_password("senha123"), role="medico"),
                User(id="22222222-2222-2222-2222-222222222222", email="medico_b@clinica.com",
                     hashed_password=HashPassword.hash_password("senha123"), role="medico"),
                User(id="00000000-0000-0000-0000-000000000000", email="admin@clinica.com",
                     hashed_password=HashPassword.hash_password("senha123"), role="admin", mfa_secret="123456"),
                User(id="lab_parceiro_01", hashed_password=HashPassword.hash_password("LabSecret#2026"), role="m2m",
                     scopes="appointments:read", is_m2m=True)
            ]
            session.add_all(users_mock)

            consultas_mock = [
                Consulta(paciente_nome="Carlos Silva", medico_nome="Dr. Roberto",
                         medico_id="11111111-1111-1111-1111-111111111111", data_hora="2026-10-15T10:00:00",
                         especialidade="Cardiologia", status="agendada",
                         anotacoes_internas="Paciente com histórico de arritmia."),
                Consulta(paciente_nome="Marina Souza", medico_nome="Dra. Ana",
                         medico_id="22222222-2222-2222-2222-222222222222", data_hora="2026-10-16T14:30:00",
                         especialidade="Dermatologia", status="concluida",
                         anotacoes_internas="Primeira consulta clínica."),
                Consulta(paciente_nome="<script>alert('Fui hackeado')</script>", medico_nome="Dra. Teste",
                         medico_id="99999999-9999-9999-9999-999999999999", data_hora="2026-10-15T10:00:00",
                         especialidade="Psiquiatria", status="agendada",
                         anotacoes_internas="DADO_SENSIVEL_NUNCA_VAZAR")
            ]
            session.add_all(consultas_mock)
            session.commit()


# Bootstrap Inicial
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Executado antes da aplicação aceitar requisições (Startup)
    create_db_and_tables()
    populate_db()
    yield


app.include_router(consultas_router)
app.include_router(admin_router)
app.include_router(user_router)


@app.get("/", tags=["Healthcheck"])
async def root():
    return {"status": "API da Clínica operando conectada ao SQLite."}