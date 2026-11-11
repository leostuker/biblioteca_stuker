import os
from contextlib import contextmanager
from psycopg2 import pool

DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = int(os.environ.get("DB_PORT", 5432))
DB_USER = os.environ.get("DB_USER", "leo")
DB_PASS = os.environ.get("DB_PASS", "1998")
DB_NAME = os.environ.get("DB_NAME", "biblioteca_stuker")

pool_conexoes = None

def iniciar_pool():
	global pool_conexoes
	if pool_conexoes is None:
		pool_conexoes = pool.ThreadedConnectionPool(
			minconn=1,
			maxconn=20,
			host=DB_HOST,
			port=DB_PORT,
			user=DB_USER,
			password=DB_PASS,
			database=DB_NAME
		)

def fechar_pool():
	global pool_conexoes
	if pool_conexoes is not None:
		pool_conexoes.closeall()
		pool_conexoes = None

@contextmanager
def obter_conexao():
	if pool_conexoes is None:
		iniciar_pool()
	conexao = pool_conexoes.getconn()
	try:
		yield conexao
		conexao.commit()
	except Exception:
		conexao.rollback()
		raise
	finally:
		pool_conexoes.putconn(conexao)

def inicializar_banco():
	ddl = """
	CREATE TABLE IF NOT EXISTS usuarios (
		id SERIAL PRIMARY KEY,
		usuario VARCHAR(50) UNIQUE NOT NULL,
		nome VARCHAR(150) NOT NULL,
		email VARCHAR(150) UNIQUE,
		senha_hash VARCHAR(255) NOT NULL,
		is_admin BOOLEAN DEFAULT FALSE,
		criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	);

	CREATE TABLE IF NOT EXISTS livros (
		id SERIAL PRIMARY KEY,
		titulo VARCHAR(255) NOT NULL,
		autor VARCHAR(255),
		isbn_13 VARCHAR(30),
		isbn_10 VARCHAR(30),
		editora VARCHAR(150),
		ano_publicacao INTEGER,
		paginas INTEGER,
		sinopse TEXT,
		capa_url TEXT,
		formato VARCHAR(30) DEFAULT 'Físico',
		disponivel BOOLEAN DEFAULT TRUE,
		criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP
	);

	CREATE TABLE IF NOT EXISTS tags (
		id SERIAL PRIMARY KEY,
		nome VARCHAR(100) UNIQUE NOT NULL
	);

	CREATE TABLE IF NOT EXISTS livro_tags (
		livro_id INTEGER REFERENCES livros(id) ON DELETE CASCADE,
		tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
		PRIMARY KEY (livro_id, tag_id)
	);

	CREATE TABLE IF NOT EXISTS leituras_usuario (
		id SERIAL PRIMARY KEY,
		usuario_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
		livro_id INTEGER REFERENCES livros(id) ON DELETE CASCADE,
		status VARCHAR(50) NOT NULL,
		atualizado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		UNIQUE (usuario_id, livro_id)
	);

	CREATE TABLE IF NOT EXISTS resenhas (
		id SERIAL PRIMARY KEY,
		usuario_id INTEGER REFERENCES usuarios(id) ON DELETE CASCADE,
		livro_id INTEGER REFERENCES livros(id) ON DELETE CASCADE,
		nota INTEGER CHECK (nota >= 1 AND nota <= 5),
		texto TEXT NOT NULL,
		criado_em TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
		UNIQUE (usuario_id, livro_id)
	);

	CREATE TABLE IF NOT EXISTS emprestimos (
		id SERIAL PRIMARY KEY,
		livro_id INTEGER REFERENCES livros(id) ON DELETE CASCADE,
		usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL,
		nome_destinatario VARCHAR(100) NOT NULL,
		contato_destinatario VARCHAR(100),
		data_emprestimo DATE DEFAULT CURRENT_DATE,
		data_devolucao_prevista DATE,
		data_devolucao_real DATE,
		observacoes TEXT,
		status VARCHAR(30) DEFAULT 'ativo'
	);

	CREATE INDEX IF NOT EXISTS idx_livros_titulo ON livros (titulo);
	CREATE INDEX IF NOT EXISTS idx_livros_autor ON livros (autor);
	"""
	with obter_conexao() as conexao:
		with conexao.cursor() as cursor:
			cursor.execute(ddl)
