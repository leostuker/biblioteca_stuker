import os
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from backend.bd import iniciar_pool, fechar_pool, inicializar_banco
from backend.servicos.usuarios_servico import garantir_admin_padrao
from backend.servicos.importador_csv import importar_libib_csv
from backend.rotas.auth_rotas import router as auth_router
from backend.rotas.catalogo_rotas import router as catalogo_router
from backend.rotas.leituras_rotas import router as leituras_router
from backend.rotas.admin_rotas import router as admin_router

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "frontend" / "static"
DADOS_CSV = BASE_DIR / "dados" / "libib.csv"

@asynccontextmanager
async def lifespan(app: FastAPI):
	iniciar_pool()
	inicializar_banco()
	garantir_admin_padrao()
	caminho_csv = str(DADOS_CSV) if DADOS_CSV.exists() else "/mnt/dados/projetos/projeto-servidor/dados/libib.csv"
	importar_libib_csv(caminho_csv)
	yield
	fechar_pool()

app = FastAPI(title="Biblioteca Stüker", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(auth_router)
app.include_router(catalogo_router)
app.include_router(leituras_router)
app.include_router(admin_router)

@app.get("/health")
def healthcheck():
	return {"status": "ok", "app": "Biblioteca Stüker"}

@app.get("/pmb")
@app.get("/pmb/{resto:path}")
def redirecionar_pmb(resto: str = ""):
	return RedirectResponse(url="/", status_code=301)

@app.exception_handler(StarletteHTTPException)
async def custom_http_exception_handler(request: Request, exc: StarletteHTTPException):
	if exc.status_code == 404 and "text/html" in request.headers.get("accept", ""):
		return RedirectResponse(url="/", status_code=302)
	return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
