from psycopg2.extras import RealDictCursor
from backend.bd import obter_conexao
from backend.seguranca import gerar_hash_senha, verificar_senha

def criar_usuario(nome, usuario, email, senha, is_admin=False):
	senha_hash = gerar_hash_senha(senha)
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute(
				"""
				INSERT INTO usuarios (nome, usuario, email, senha_hash, is_admin)
				VALUES (%s, %s, %s, %s, %s)
				RETURNING id, nome, usuario, email, is_admin, criado_em
				""",
				(nome.strip(), usuario.strip().lower(), email.strip().lower() if email else None, senha_hash, bool(is_admin))
			)
			novo_usuario = cursor.fetchone()
			return dict(novo_usuario)

def autenticar_usuario(login, senha):
	identificador = login.strip().lower()
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute(
				"""
				SELECT id, nome, usuario, email, senha_hash, is_admin, criado_em
				FROM usuarios
				WHERE LOWER(usuario) = %s OR LOWER(email) = %s
				""",
				(identificador, identificador)
			)
			registro = cursor.fetchone()
			if registro and verificar_senha(senha, registro["senha_hash"]):
				dados = dict(registro)
				dados.pop("senha_hash", None)
				return dados
			return None

def listar_usuarios():
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute(
				"""
				SELECT id, nome, usuario, email, is_admin, criado_em
				FROM usuarios
				ORDER BY nome ASC
				"""
			)
			return [dict(linha) for linha in cursor.fetchall()]

def alternar_perfil_admin(usuario_id):
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute(
				"""
				UPDATE usuarios
				SET is_admin = NOT is_admin
				WHERE id = %s
				RETURNING id, nome, usuario, email, is_admin
				""",
				(usuario_id,)
			)
			atualizado = cursor.fetchone()
			return dict(atualizado) if atualizado else None

def excluir_usuario(usuario_id):
	with obter_conexao() as conexao:
		with conexao.cursor() as cursor:
			cursor.execute("DELETE FROM usuarios WHERE id = %s", (usuario_id,))
			return cursor.rowcount > 0

def garantir_admin_padrao():
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute(
				"SELECT id FROM usuarios WHERE LOWER(usuario) = %s OR LOWER(email) = %s",
				("leo", "leo@stuker.dev")
			)
			existente = cursor.fetchone()
			if not existente:
				senha_hash = gerar_hash_senha("1998")
				cursor.execute(
					"""
					INSERT INTO usuarios (nome, usuario, email, senha_hash, is_admin)
					VALUES (%s, %s, %s, %s, TRUE)
					""",
					("Leonardo Stüker", "leo", "leo@stuker.dev", senha_hash)
				)
