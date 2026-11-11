from psycopg2.extras import RealDictCursor
from backend.bd import obter_conexao

STATUS_VALIDOS = {"quero_ler", "lendo", "lido", "abandonado"}

def obter_leituras_usuario(usuario_id):
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute(
				"""
				SELECT
					lei.id AS leitura_id,
					lei.status,
					lei.atualizado_em,
					l.id AS livro_id,
					l.titulo,
					l.autor,
					l.capa_url,
					l.paginas,
					l.ano_publicacao,
					l.disponivel,
					r.nota AS minha_nota,
					r.texto AS minha_resenha
				FROM leituras_usuario lei
				JOIN livros l ON l.id = lei.livro_id
				LEFT JOIN resenhas r ON r.livro_id = l.id AND r.usuario_id = lei.usuario_id
				WHERE lei.usuario_id = %s
				ORDER BY l.titulo ASC
				""",
				(usuario_id,)
			)
			registros = [dict(linha) for linha in cursor.fetchall()]
			agrupado = {
				"quero_ler": [],
				"lendo": [],
				"lido": [],
				"abandonado": [],
				"todos": registros
			}
			for item in registros:
				status = item.get("status")
				if status in agrupado:
					agrupado[status].append(item)
			return agrupado

def obter_status_leitura_livro(usuario_id, livro_id):
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute(
				"SELECT status FROM leituras_usuario WHERE usuario_id = %s AND livro_id = %s",
				(usuario_id, livro_id)
			)
			linha = cursor.fetchone()
			return linha["status"] if linha else None

def atualizar_status_leitura(usuario_id, livro_id, status):
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			if not status or status == "remover":
				cursor.execute(
					"DELETE FROM leituras_usuario WHERE usuario_id = %s AND livro_id = %s",
					(usuario_id, livro_id)
				)
				return None

			status_limpo = status.strip().lower()
			if status_limpo not in STATUS_VALIDOS:
				raise ValueError(f"Status de leitura inválido: {status}")

			cursor.execute(
				"""
				INSERT INTO leituras_usuario (usuario_id, livro_id, status, atualizado_em)
				VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
				ON CONFLICT (usuario_id, livro_id)
				DO UPDATE SET
					status = EXCLUDED.status,
					atualizado_em = CURRENT_TIMESTAMP
				RETURNING id, usuario_id, livro_id, status, atualizado_em
				""",
				(usuario_id, livro_id, status_limpo)
			)
			resultado = cursor.fetchone()
			return dict(resultado)

def obter_resenha_usuario(usuario_id, livro_id):
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute(
				"SELECT id, nota, texto, criado_em FROM resenhas WHERE usuario_id = %s AND livro_id = %s",
				(usuario_id, livro_id)
			)
			linha = cursor.fetchone()
			return dict(linha) if linha else None

def salvar_resenha(usuario_id, livro_id, nota, texto):
	nota_int = int(nota)
	if nota_int < 1 or nota_int > 5:
		raise ValueError("A nota deve estar entre 1 e 5")

	texto_limpo = texto.strip() if texto else ""
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute(
				"""
				INSERT INTO resenhas (usuario_id, livro_id, nota, texto, criado_em)
				VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)
				ON CONFLICT (usuario_id, livro_id)
				DO UPDATE SET
					nota = EXCLUDED.nota,
					texto = EXCLUDED.texto
				RETURNING id, usuario_id, livro_id, nota, texto, criado_em
				""",
				(usuario_id, livro_id, nota_int, texto_limpo)
			)
			resenha = cursor.fetchone()
			return dict(resenha)
