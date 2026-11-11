import asyncio
import os
from pathlib import Path
from contextlib import asynccontextmanager, contextmanager

import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import RealDictCursor

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

db_pool = None

def criar_pool_conexoes():
	return ThreadedConnectionPool(
		minconn=1,
		maxconn=10,
		host=os.environ.get("DB_HOST", "postgres"),
		port=int(os.environ.get("DB_PORT", 5432)),
		database=os.environ.get("DB_NAME", "biblioteca_stuker"),
		user=os.environ.get("DB_USER", "leo"),
		password=os.environ.get("DB_PASS", "1998")
	)

@contextmanager
def obter_conexao():
	if not db_pool:
		raise HTTPException(
			status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
			detail="Banco de dados indisponivel"
		)
	conexao = db_pool.getconn()
	try:
		yield conexao
	finally:
		db_pool.putconn(conexao)

@asynccontextmanager
async def lifespan(app: FastAPI):
	global db_pool
	tentativas = 5
	intervalo = 2
	for tentativa in range(1, tentativas + 1):
		try:
			db_pool = criar_pool_conexoes()
			break
		except Exception:
			if tentativa < tentativas:
				await asyncio.sleep(intervalo)
			else:
				db_pool = None
	yield
	if db_pool:
		db_pool.closeall()

app = FastAPI(title="Biblioteca Stüker API", lifespan=lifespan)

app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_methods=["*"],
	allow_headers=["*"]
)

@app.middleware("http")
async def adicionar_cabecalhos_seguranca(requisicao: Request, call_next):
	resposta = await call_next(requisicao)
	resposta.headers["X-Content-Type-Options"] = "nosniff"
	resposta.headers["X-Frame-Options"] = "DENY"
	return resposta

app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR / "static")), name="static")

@app.get("/health")
def healthcheck():
	return {"status": "ok"}

@app.get("/")
def pagina_inicial():
	return FileResponse(FRONTEND_DIR / "index.html")

@app.get("/api/livros")
def listar_livros():
	if not db_pool:
		return []
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute("SELECT id, titulo, autor, ano, genero FROM livros ORDER BY titulo ASC")
			return cursor.fetchall()
