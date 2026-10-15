import asyncio
import json
import os
import re
import urllib.error
import urllib.request
from contextlib import asynccontextmanager, contextmanager
from datetime import date
from pathlib import Path
from typing import Literal, Optional

from psycopg2 import errors as erros_pg
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.seguranca import (
	VALIDADE_TOKEN_SEGUNDOS,
	criar_token,
	gerar_hash_senha,
	validar_token,
	verificar_senha,
)

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"
COOKIE_SESSAO = "sessao_biblioteca"

StatusLeitura = Literal["quero_ler", "lendo", "lido", "abandonado"]

LIVRO_EMPRESTADO_SQL = "EXISTS (SELECT 1 FROM emprestimos e WHERE e.id_livro = l.id_livro AND e.status = 'ativo')"

db_pool = None


def criar_db_pool():
	return ThreadedConnectionPool(
		1, 20,
		host=os.getenv("DB_HOST", "localhost"),
		port=os.getenv("DB_PORT", "5432"),
		user=os.getenv("DB_USER"),
		password=os.getenv("DB_PASS"),
		dbname=os.getenv("DB_NAME"),
		cursor_factory=RealDictCursor,
	)


@contextmanager
def get_db_connection():
	global db_pool
	if db_pool is None:
		try:
			db_pool = criar_db_pool()
		except Exception as erro:
			raise HTTPException(
				status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
				detail=f"Banco de dados não disponível: {erro}",
			)
	conexao = db_pool.getconn()
	try:
		yield conexao
	except Exception:
		conexao.rollback()
		raise
	finally:
		db_pool.putconn(conexao)


def escapar_like(texto: str) -> str:
	return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def normalizar_isbn(texto: Optional[str]) -> Optional[str]:
	if not texto:
		return None
	apenas_digitos = re.sub(r"[^0-9Xx]", "", texto).upper()
	return apenas_digitos or None


def inserir_usuario(cursor, dados, is_admin: bool):
	cursor.execute(
		"""
		INSERT INTO usuarios (nome, email, telefone, senha_hash, is_admin)
		VALUES (%s, %s, %s, %s, %s)
		RETURNING id_usuario, nome, email, telefone, is_admin
		""",
		(dados.nome, dados.email, dados.telefone, gerar_hash_senha(dados.senha), is_admin),
	)
	return cursor.fetchone()


def garantir_admin_inicial():
	email = os.getenv("ADMIN_EMAIL")
	senha = os.getenv("ADMIN_PASS")
	if not email or not senha:
		return
	with get_db_connection() as conexao:
		with conexao.cursor() as cursor:
			cursor.execute("SELECT 1 FROM usuarios WHERE is_admin LIMIT 1")
			if cursor.fetchone():
				return
			dados = CadastroEntrada(nome=os.getenv("ADMIN_NOME", "Administrador"), email=email, senha=senha)
			inserir_usuario(cursor, dados, is_admin=True)
		conexao.commit()


@asynccontextmanager
async def lifespan(app):
	global db_pool
	tentativas = 10
	intervalo = 3
	for tentativa in range(tentativas):
		try:
			db_pool = criar_db_pool()
			print("Conectado ao PostgreSQL!")
			break
		except Exception as erro:
			print(f"Tentativa {tentativa + 1}/{tentativas} falhou: {erro}")
			if tentativa < tentativas - 1:
				await asyncio.sleep(intervalo)
	if db_pool:
		garantir_admin_inicial()
	yield
	if db_pool:
		db_pool.closeall()
		db_pool = None


app = FastAPI(title="Biblioteca Stüker", lifespan=lifespan)

CABECALHOS_SEGURANCA = {
	"Content-Security-Policy": (
		"default-src 'self'; "
		"img-src 'self' https: data:; "
		"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
		"font-src https://fonts.gstatic.com; "
		"script-src 'self' https://unpkg.com; "
		"media-src 'self' blob:; "
		"connect-src 'self'; "
		"frame-ancestors 'none'; "
		"base-uri 'self'; "
		"form-action 'self'"
	),
	"Strict-Transport-Security": "max-age=31536000; includeSubDomains",
	"X-Content-Type-Options": "nosniff",
	"X-Frame-Options": "DENY",
	"Referrer-Policy": "same-origin",
	"Permissions-Policy": "camera=(self)",
}


@app.middleware("http")
async def adicionar_cabecalhos_seguranca(request: Request, call_next):
	resposta = await call_next(request)
	for nome, valor in CABECALHOS_SEGURANCA.items():
		resposta.headers[nome] = valor
	return resposta


class ModeloBase(BaseModel):
	model_config = ConfigDict(str_strip_whitespace=True)


class CadastroEntrada(ModeloBase):
	nome: str = Field(min_length=1, max_length=255)
	email: str = Field(min_length=3, max_length=255)
	telefone: Optional[str] = Field(default=None, max_length=50)
	senha: str = Field(min_length=8, max_length=128)

	@field_validator("email")
	@classmethod
	def validar_email(cls, valor):
		if "@" not in valor:
			raise ValueError("E-mail inválido")
		return valor.lower()


class LoginEntrada(ModeloBase):
	email: str
	senha: str


class LivroEntrada(ModeloBase):
	titulo: str = Field(min_length=1, max_length=255)
	autor: str = Field(min_length=1, max_length=255)
	genero: Optional[str] = Field(default=None, max_length=100)
	ano_publicacao: Optional[int] = Field(default=None, ge=0, le=3000)
	numero_paginas: Optional[int] = Field(default=None, ge=1)
	isbn: Optional[str] = None
	url_capa: Optional[str] = None
	sinopse: Optional[str] = None

	@field_validator("isbn")
	@classmethod
	def validar_isbn(cls, valor):
		return normalizar_isbn(valor)

	@field_validator("url_capa")
	@classmethod
	def validar_url_capa(cls, valor):
		if valor and not valor.startswith(("http://", "https://")):
			raise ValueError("URL da capa inválida")
		return valor or None


class AvaliacaoEntrada(ModeloBase):
	status: StatusLeitura
	nota: Optional[int] = Field(default=None, ge=1, le=5)
	resenha: Optional[str] = None
	data_inicio: Optional[date] = None
	data_conclusao: Optional[date] = None


class EmprestimoEntrada(ModeloBase):
	id_livro: int
	id_usuario: int
	data_prevista: date
	observacao: Optional[str] = None


def extrair_token(request: Request) -> Optional[str]:
	cabecalho = request.headers.get("authorization", "")
	if cabecalho.lower().startswith("bearer "):
		return cabecalho[7:].strip()
	return request.cookies.get(COOKIE_SESSAO)


def usuario_atual(request: Request):
	token = extrair_token(request)
	id_usuario = validar_token(token) if token else None
	if id_usuario is None:
		return None
	with get_db_connection() as conexao:
		with conexao.cursor() as cursor:
			cursor.execute(
				"SELECT id_usuario, nome, email, telefone, is_admin FROM usuarios WHERE id_usuario = %s",
				(id_usuario,),
			)
			return cursor.fetchone()


def exigir_login(usuario=Depends(usuario_atual)):
	if usuario is None:
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Faça login para continuar")
	return usuario


def exigir_admin(usuario=Depends(exigir_login)):
	if not usuario["is_admin"]:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Apenas o administrador pode fazer isso")
	return usuario


def abrir_sessao(response: Response, usuario):
	token = criar_token(usuario["id_usuario"])
	response.set_cookie(
		COOKIE_SESSAO,
		token,
		httponly=True,
		samesite="lax",
		secure=os.getenv("COOKIE_SEGURO", "false").lower() == "true",
		max_age=VALIDADE_TOKEN_SEGUNDOS,
	)
	return {"token": token, "usuario": usuario}


@app.get("/health")
def health():
	with get_db_connection() as conexao:
		with conexao.cursor() as cursor:
			cursor.execute("SELECT 1")
	return {"status": "ok"}


@app.post("/api/auth/cadastro", status_code=status.HTTP_201_CREATED)
def cadastrar_leitor(dados: CadastroEntrada, response: Response):
	with get_db_connection() as conexao:
		with conexao.cursor() as cursor:
			try:
				usuario = inserir_usuario(cursor, dados, is_admin=False)
			except erros_pg.UniqueViolation:
				raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado")
		conexao.commit()
	return abrir_sessao(response, usuario)


@app.post("/api/auth/login")
def entrar(dados: LoginEntrada, response: Response):
	with get_db_connection() as conexao:
		with conexao.cursor() as cursor:
			cursor.execute(
				"SELECT id_usuario, nome, email, telefone, is_admin, senha_hash FROM usuarios WHERE email = %s",
				(dados.email.strip().lower(),),
			)
			registro = cursor.fetchone()
	if not registro or not verificar_senha(dados.senha, registro["senha_hash"]):
		raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="E-mail ou senha incorretos")
	registro.pop("senha_hash")
	return abrir_sessao(response, registro)


@app.post("/api/auth/logout")
def sair(response: Response):
	response.delete_cookie(COOKIE_SESSAO)
	return {"ok": True}


@app.get("/api/auth/me")
def quem_sou_eu(usuario=Depends(usuario_atual)):
	return {"usuario": usuario}


@app.get("/api/usuarios")
def listar_usuarios(_admin=Depends(exigir_admin)):
	with get_db_connection() as conexao:
		with conexao.cursor() as cursor:
			cursor.execute("SELECT id_usuario, nome, email, telefone, is_admin FROM usuarios ORDER BY nome")
			return cursor.fetchall()


@app.post("/api/usuarios", status_code=status.HTTP_201_CREATED)
def criar_usuario(dados: CadastroEntrada, _admin=Depends(exigir_admin)):
	with get_db_connection() as conexao:
		with conexao.cursor() as cursor:
			try:
				usuario = inserir_usuario(cursor, dados, is_admin=False)
			except erros_pg.UniqueViolation:
				raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="E-mail já cadastrado")
		conexao.commit()
	return usuario


@app.get("/api/resumo")
def resumo():
	with get_db_connection() as conexao:
		with conexao.cursor() as cursor:
			cursor.execute(
				"""
				SELECT
					(SELECT COUNT(*) FROM livros) AS total_livros,
					(SELECT COUNT(*) FROM emprestimos WHERE status = 'ativo') AS emprestados,
					(SELECT COUNT(*) FROM avaliacoes WHERE status = 'lido') AS leituras_concluidas
				"""
			)
			contadores = cursor.fetchone()
			cursor.execute("SELECT DISTINCT genero FROM livros WHERE genero IS NOT NULL ORDER BY genero")
			contadores["generos"] = [linha["genero"] for linha in cursor.fetchall()]
	return contadores


@app.get("/api/livros")
def listar_livros(
	busca: Optional[str] = None,
	genero: Optional[str] = None,
	status_leitura: Optional[StatusLeitura] = None,
	disponivel: Optional[bool] = None,
	usuario=Depends(usuario_atual),
):
	id_usuario = usuario["id_usuario"] if usuario else None
	condicoes = []
	parametros = [id_usuario]
	if busca:
		padrao = f"%{escapar_like(busca)}%"
		condicoes.append("(l.titulo ILIKE %s OR l.autor ILIKE %s OR l.isbn ILIKE %s)")
		parametros += [padrao, padrao, padrao]
	if genero:
		condicoes.append("l.genero = %s")
		parametros.append(genero)
	if status_leitura:
		condicoes.append(
			"EXISTS (SELECT 1 FROM avaliacoes m WHERE m.id_livro = l.id_livro AND m.id_usuario = %s AND m.status = %s::status_leitura)"
		)
		parametros += [id_usuario, status_leitura]
	if disponivel is not None:
		condicoes.append(f"{'NOT ' if disponivel else ''}{LIVRO_EMPRESTADO_SQL}")
	filtro = f"WHERE {' AND '.join(condicoes)}" if condicoes else ""
	with get_db_connection() as conexao:
		with conexao.cursor() as cursor:
			cursor.execute(
				f"""
				SELECT l.id_livro, l.titulo, l.autor, l.genero, l.ano_publicacao, l.url_capa,
					ROUND(AVG(a.nota), 1) AS nota_media,
					NOT {LIVRO_EMPRESTADO_SQL} AS disponivel,
					(SELECT m.status FROM avaliacoes m WHERE m.id_livro = l.id_livro AND m.id_usuario = %s) AS meu_status
				FROM livros l
				LEFT JOIN avaliacoes a ON a.id_livro = l.id_livro
				{filtro}
				GROUP BY l.id_livro
				ORDER BY l.titulo
				""",
				parametros,
			)
			return cursor.fetchall()


@app.get("/api/livros/{id_livro}")
def detalhar_livro(id_livro: int, usuario=Depends(usuario_atual)):
	id_usuario = usuario["id_usuario"] if usuario else None
	eh_admin = bool(usuario and usuario["is_admin"])
	with get_db_connection() as conexao:
		with conexao.cursor() as cursor:
			cursor.execute(
				f"""
				SELECT l.*,
					(SELECT ROUND(AVG(nota), 1) FROM avaliacoes WHERE id_livro = l.id_livro) AS nota_media,
					(SELECT COUNT(nota) FROM avaliacoes WHERE id_livro = l.id_livro) AS total_notas,
					NOT {LIVRO_EMPRESTADO_SQL} AS disponivel
				FROM livros l
				WHERE l.id_livro = %s
				""",
				(id_livro,),
			)
			livro = cursor.fetchone()
			if not livro:
				raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Livro não encontrado")
			cursor.execute(
				"""
				SELECT u.nome, a.status, a.nota, a.resenha, a.data_conclusao, a.data_atualizacao
				FROM avaliacoes a
				JOIN usuarios u ON u.id_usuario = a.id_usuario
				WHERE a.id_livro = %s AND (a.nota IS NOT NULL OR COALESCE(a.resenha, '') <> '')
				ORDER BY a.data_atualizacao DESC
				""",
				(id_livro,),
			)
			livro["avaliacoes"] = cursor.fetchall()
			cursor.execute(
				"""
				SELECT status, nota, resenha, data_inicio, data_conclusao
				FROM avaliacoes WHERE id_livro = %s AND id_usuario = %s
				""",
				(id_livro, id_usuario),
			)
			livro["minha_avaliacao"] = cursor.fetchone()
			livro["emprestimo_ativo"] = None
			livro["historico_emprestimos"] = []
			if eh_admin:
				cursor.execute(
					"""
					SELECT e.id_emprestimo, u.nome AS nome_usuario, u.telefone, e.data_emprestimo,
						e.data_prevista, e.data_devolucao, e.status, e.observacao,
						(e.status = 'ativo' AND e.data_prevista < CURRENT_DATE) AS atrasado
					FROM emprestimos e
					JOIN usuarios u ON u.id_usuario = e.id_usuario
					WHERE e.id_livro = %s
					ORDER BY e.data_emprestimo DESC, e.id_emprestimo DESC
					""",
					(id_livro,),
				)
				historico = cursor.fetchall()
				livro["historico_emprestimos"] = historico
				livro["emprestimo_ativo"] = next((item for item in historico if item["status"] == "ativo"), None)
	return livro


@app.post("/api/livros", status_code=status.HTTP_201_CREATED)
def cadastrar_livro(dados: LivroEntrada, _admin=Depends(exigir_admin)):
	with get_db_connection() as conexao:
		with conexao.cursor() as cursor:
			try:
				cursor.execute(
					"""
					INSERT INTO livros (titulo, autor, genero, ano_publicacao, numero_paginas, isbn, url_capa, sinopse)
					VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
					RETURNING id_livro
					""",
					(dados.titulo, dados.autor, dados.genero, dados.ano_publicacao, dados.numero_paginas,
						dados.isbn, dados.url_capa, dados.sinopse),
				)
			except erros_pg.UniqueViolation:
				raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Já existe um livro com esse ISBN")
			livro = cursor.fetchone()
		conexao.commit()
	return livro


@app.put("/api/livros/{id_livro}")
def editar_livro(id_livro: int, dados: LivroEntrada, _admin=Depends(exigir_admin)):
	with get_db_connection() as conexao:
		with conexao.cursor() as cursor:
			try:
				cursor.execute(
					"""
					UPDATE livros
					SET titulo = %s, autor = %s, genero = %s, ano_publicacao = %s,
						numero_paginas = %s, isbn = %s, url_capa = %s, sinopse = %s
					WHERE id_livro = %s
					RETURNING id_livro
					""",
					(dados.titulo, dados.autor, dados.genero, dados.ano_publicacao, dados.numero_paginas,
						dados.isbn, dados.url_capa, dados.sinopse, id_livro),
				)
			except erros_pg.UniqueViolation:
				raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Já existe um livro com esse ISBN")
			livro = cursor.fetchone()
		conexao.commit()
	if not livro:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Livro não encontrado")
	return livro


@app.delete("/api/livros/{id_livro}")
def excluir_livro(id_livro: int, _admin=Depends(exigir_admin)):
	with get_db_connection() as conexao:
		with conexao.cursor() as cursor:
			cursor.execute("DELETE FROM livros WHERE id_livro = %s RETURNING id_livro", (id_livro,))
			removido = cursor.fetchone()
		conexao.commit()
	if not removido:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Livro não encontrado")
	return {"ok": True}


@app.post("/api/livros/{id_livro}/avaliacao")
def salvar_avaliacao(id_livro: int, dados: AvaliacaoEntrada, usuario=Depends(exigir_login)):
	with get_db_connection() as conexao:
		with conexao.cursor() as cursor:
			try:
				cursor.execute(
					"""
					INSERT INTO avaliacoes (id_livro, id_usuario, status, nota, resenha, data_inicio, data_conclusao)
					VALUES (%s, %s, %s::status_leitura, %s, %s, %s, %s)
					ON CONFLICT (id_livro, id_usuario) DO UPDATE SET
						status = EXCLUDED.status,
						nota = EXCLUDED.nota,
						resenha = EXCLUDED.resenha,
						data_inicio = EXCLUDED.data_inicio,
						data_conclusao = EXCLUDED.data_conclusao,
						data_atualizacao = CURRENT_TIMESTAMP
					RETURNING id_avaliacao
					""",
					(id_livro, usuario["id_usuario"], dados.status, dados.nota, dados.resenha or None,
						dados.data_inicio, dados.data_conclusao),
				)
			except erros_pg.ForeignKeyViolation:
				raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Livro não encontrado")
			avaliacao = cursor.fetchone()
		conexao.commit()
	return avaliacao


def requisitar_json(url: str):
	requisicao = urllib.request.Request(url, headers={"User-Agent": "BibliotecaStuker/1.0"})
	try:
		with urllib.request.urlopen(requisicao, timeout=8) as resposta:
			return json.loads(resposta.read().decode("utf-8"))
	except (urllib.error.URLError, TimeoutError, ValueError):
		return None


def extrair_ano(texto: Optional[str]) -> Optional[int]:
	correspondencia = re.search(r"\d{4}", texto or "")
	return int(correspondencia.group()) if correspondencia else None


def buscar_google_books(isbn: str):
	dados = requisitar_json(f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn}")
	if not dados or not dados.get("items"):
		return None
	informacoes = dados["items"][0]["volumeInfo"]
	capa = informacoes.get("imageLinks", {}).get("thumbnail")
	return {
		"titulo": informacoes.get("title"),
		"autor": ", ".join(informacoes.get("authors", [])),
		"genero": (informacoes.get("categories") or [None])[0],
		"ano_publicacao": extrair_ano(informacoes.get("publishedDate")),
		"numero_paginas": informacoes.get("pageCount") or None,
		"isbn": isbn,
		"url_capa": capa.replace("http://", "https://") if capa else None,
		"sinopse": informacoes.get("description"),
	}


def buscar_open_library(isbn: str):
	chave = f"ISBN:{isbn}"
	dados = requisitar_json(f"https://openlibrary.org/api/books?bibkeys={chave}&format=json&jscmd=data")
	if not dados or chave not in dados:
		return None
	informacoes = dados[chave]
	capas = informacoes.get("cover", {})
	assuntos = informacoes.get("subjects") or [{}]
	autores = informacoes.get("authors", [])
	return {
		"titulo": informacoes.get("title"),
		"autor": ", ".join(autor["name"] for autor in autores),
		"genero": assuntos[0].get("name"),
		"ano_publicacao": extrair_ano(informacoes.get("publish_date")),
		"numero_paginas": informacoes.get("number_of_pages"),
		"isbn": isbn,
		"url_capa": capas.get("large") or capas.get("medium"),
		"sinopse": None,
	}


@app.get("/api/isbn/{codigo}")
def consultar_isbn(codigo: str, _admin=Depends(exigir_admin)):
	isbn = normalizar_isbn(codigo)
	if not isbn or len(isbn) not in (10, 13):
		raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="ISBN deve ter 10 ou 13 dígitos")
	resultados = [r for r in (buscar_google_books(isbn), buscar_open_library(isbn)) if r]
	if not resultados:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="ISBN não encontrado nas bases públicas")
	return {campo: next((r[campo] for r in resultados if r[campo]), None) for campo in resultados[0]}


@app.get("/api/emprestimos")
def listar_emprestimos(usuario=Depends(exigir_login)):
	with get_db_connection() as conexao:
		with conexao.cursor() as cursor:
			cursor.execute(
				"""
				SELECT e.id_emprestimo, e.id_livro, l.titulo, l.autor, e.id_usuario,
					u.nome AS nome_usuario, u.telefone, e.data_emprestimo, e.data_prevista,
					e.data_devolucao, e.status, e.observacao,
					(e.status = 'ativo' AND e.data_prevista < CURRENT_DATE) AS atrasado
				FROM emprestimos e
				JOIN livros l ON l.id_livro = e.id_livro
				JOIN usuarios u ON u.id_usuario = e.id_usuario
				WHERE %s OR e.id_usuario = %s
				ORDER BY (e.status = 'ativo') DESC, e.data_prevista, e.id_emprestimo DESC
				""",
				(usuario["is_admin"], usuario["id_usuario"]),
			)
			return cursor.fetchall()


@app.post("/api/emprestimos", status_code=status.HTTP_201_CREATED)
def registrar_emprestimo(dados: EmprestimoEntrada, _admin=Depends(exigir_admin)):
	if dados.data_prevista < date.today():
		raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="A data prevista não pode estar no passado")
	with get_db_connection() as conexao:
		with conexao.cursor() as cursor:
			try:
				cursor.execute(
					"""
					INSERT INTO emprestimos (id_livro, id_usuario, data_prevista, observacao)
					VALUES (%s, %s, %s, %s)
					RETURNING id_emprestimo
					""",
					(dados.id_livro, dados.id_usuario, dados.data_prevista, dados.observacao or None),
				)
			except erros_pg.UniqueViolation:
				raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Este livro já está emprestado")
			except erros_pg.ForeignKeyViolation:
				raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Livro ou usuário não encontrado")
			emprestimo = cursor.fetchone()
		conexao.commit()
	return emprestimo


@app.put("/api/emprestimos/{id_emprestimo}/devolver")
def devolver_emprestimo(id_emprestimo: int, _admin=Depends(exigir_admin)):
	with get_db_connection() as conexao:
		with conexao.cursor() as cursor:
			cursor.execute(
				"""
				UPDATE emprestimos
				SET status = 'devolvido', data_devolucao = CURRENT_DATE
				WHERE id_emprestimo = %s AND status = 'ativo'
				RETURNING id_emprestimo
				""",
				(id_emprestimo,),
			)
			devolvido = cursor.fetchone()
		conexao.commit()
	if not devolvido:
		raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Empréstimo ativo não encontrado")
	return {"ok": True}


def pagina(nome_arquivo: str) -> FileResponse:
	return FileResponse(FRONTEND_DIR / nome_arquivo)


@app.get("/", include_in_schema=False)
def pagina_catalogo():
	return pagina("index.html")


@app.get("/livro/{id_livro}", include_in_schema=False)
def pagina_livro(id_livro: int):
	return pagina("livro.html")


@app.get("/emprestimos", include_in_schema=False)
def pagina_emprestimos():
	return pagina("emprestimos.html")


@app.get("/adicionar", include_in_schema=False)
def pagina_adicionar():
	return pagina("adicionar.html")


@app.get("/login", include_in_schema=False)
def pagina_login():
	return pagina("login.html")


app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")
