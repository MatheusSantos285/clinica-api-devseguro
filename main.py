from fastapi import FastAPI
from routes.consultas import router as consultas_router
from routes.admin import router as admin_router
from routes.user import router as user_router

# Ponto de entrada (entrypoint) da aplicação
app = FastAPI(title="Clínica Médica - API de Agendamento")

# Registrar (incluir) os routers dos diferentes domínios
app.include_router(consultas_router)
app.include_router(admin_router)
app.include_router(user_router)

@app.get("/", tags=["Healthcheck"])
async def root():
    return {"status": "API da Clínica Médica operando normalmente."}