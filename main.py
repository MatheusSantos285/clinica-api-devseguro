from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from config.rate_limiter import limiter

from routes.consultas import router as consultas_router
from routes.admin import router as admin_router
from routes.user import router as user_router

# Ponto de entrada (entrypoint) da aplicação
app = FastAPI(title="Clínica Médica - API de Agendamento")

# =========================================================================
# CONFIGURAÇÃO DE RATE LIMITING (SLOWAPI)
# =========================================================================
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# =========================================================================
# CONFIGURAÇÃO DE CORS (Allowlist Explícita)
# =========================================================================
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://parceiro-autorizado.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# =========================================================================
# MIDDLEWARE DE CABEÇALHOS DE SEGURANÇA HTTP
# =========================================================================
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

# Registrar (incluir) os routers dos diferentes domínios
app.include_router(consultas_router)
app.include_router(admin_router)
app.include_router(user_router)

@app.get("/", tags=["Healthcheck"])
async def root():
    return {"status": "API da Clínica Médica operando normalmente."}