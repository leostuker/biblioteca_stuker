import os
from pathlib import Path

import psycopg2
import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("SECRET_KEY", "chave-de-teste")
os.environ["ADMIN_NOME"] = "Admin Teste"
os.environ["ADMIN_EMAIL"] = "admin@teste.com"
os.environ["ADMIN_PASS"] = "senha-admin-123"

RAIZ_PROJETO = Path(__file__).resolve().parent.parent
SENHA_PADRAO = "senha-leitor-123"


@pytest.fixture(scope="session")
def banco_de_teste():
	nome_banco = os.getenv("TEST_DB_NAME")
	if not nome_banco:
		pytest.skip("Defina TEST_DB_NAME (um banco exclusivo de teste) para rodar os testes com banco")
	os.environ["DB_NAME"] = nome_banco
	conexao = psycopg2.connect(
		host=os.getenv("DB_HOST", "localhost"),
		port=os.getenv("DB_PORT", "5432"),
		user=os.getenv("DB_USER"),
		password=os.getenv("DB_PASS"),
		dbname=nome_banco,
	)
	conexao.autocommit = True
	with conexao.cursor() as cursor:
		cursor.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
		cursor.execute((RAIZ_PROJETO / "init.sql").read_text(encoding="utf-8"))
	conexao.close()


@pytest.fixture
def cliente(banco_de_teste):
	conexao = psycopg2.connect(
		host=os.getenv("DB_HOST", "localhost"),
		port=os.getenv("DB_PORT", "5432"),
		user=os.getenv("DB_USER"),
		password=os.getenv("DB_PASS"),
		dbname=os.environ["DB_NAME"],
	)
	conexao.autocommit = True
	with conexao.cursor() as cursor:
		cursor.execute("TRUNCATE usuarios, livros, avaliacoes, emprestimos RESTART IDENTITY CASCADE")
	conexao.close()
	from backend.main import app
	with TestClient(app) as cliente_teste:
		yield cliente_teste


def entrar(cliente, email, senha):
	resposta = cliente.post("/api/auth/login", json={"email": email, "senha": senha})
	assert resposta.status_code == 200
	cliente.cookies.clear()
	return {"Authorization": f"Bearer {resposta.json()['token']}"}


@pytest.fixture
def cabecalho_admin(cliente):
	return entrar(cliente, "admin@teste.com", "senha-admin-123")


@pytest.fixture
def criar_leitor(cliente):
	def criar(email, nome="Leitor"):
		resposta = cliente.post("/api/auth/cadastro", json={"nome": nome, "email": email, "senha": SENHA_PADRAO})
		assert resposta.status_code == 201
		cliente.cookies.clear()
		return {
			"cabecalho": {"Authorization": f"Bearer {resposta.json()['token']}"},
			"id_usuario": resposta.json()["usuario"]["id_usuario"],
		}
	return criar


@pytest.fixture
def criar_livro(cliente, cabecalho_admin):
	def criar(titulo="Dom Casmurro", autor="Machado de Assis", **extras):
		corpo = {"titulo": titulo, "autor": autor, **extras}
		resposta = cliente.post("/api/livros", json=corpo, headers=cabecalho_admin)
		assert resposta.status_code == 201
		return resposta.json()["id_livro"]
	return criar
