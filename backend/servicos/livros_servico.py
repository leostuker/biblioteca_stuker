from psycopg2.extras import RealDictCursor
from backend.bd import obter_conexao

def _sincronizar_tags_livro(cursor, livro_id, tags_lista):
	cursor.execute("DELETE FROM livro_tags WHERE livro_id = %s", (livro_id,))
	if not tags_lista:
		return
	tags_limpas = set()
	for tag in tags_lista:
		if tag and str(tag).strip():
			tags_limpas.add(str(tag).strip().lower())
	for nome_tag in tags_limpas:
		cursor.execute(
			"""
			INSERT INTO tags (nome)
			VALUES (%s)
			ON CONFLICT (nome) DO UPDATE SET nome = EXCLUDED.nome
			RETURNING id
			""",
			(nome_tag,)
		)
		tag_id = cursor.fetchone()["id"]
		cursor.execute(
			"""
			INSERT INTO livro_tags (livro_id, tag_id)
			VALUES (%s, %s)
			ON CONFLICT DO NOTHING
			""",
			(livro_id, tag_id)
		)

def listar_livros(termo_busca=None, tag=None):
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			condicoes = []
			parametros = []

			if termo_busca and termo_busca.strip():
				termo = f"%{termo_busca.strip()}%"
				condicoes.append("(l.titulo ILIKE %s OR l.autor ILIKE %s OR l.isbn_13 ILIKE %s OR l.isbn_10 ILIKE %s OR l.editora ILIKE %s)")
				parametros.extend([termo, termo, termo, termo, termo])

			if tag and tag.strip():
				condicoes.append(
					"""
					EXISTS (
						SELECT 1 FROM livro_tags lt2
						JOIN tags t2 ON t2.id = lt2.tag_id
						WHERE lt2.livro_id = l.id AND LOWER(t2.nome) = LOWER(%s)
					)
					"""
				)
				parametros.append(tag.strip())

			clausula_where = ""
			if condicoes:
				clausula_where = "WHERE " + " AND ".join(condicoes)

			consulta = f"""
				SELECT
					l.*,
					COALESCE(
						ARRAY_AGG(DISTINCT t.nome) FILTER (WHERE t.nome IS NOT NULL),
						'{{}}'
					) AS tags
				FROM livros l
				LEFT JOIN livro_tags lt ON lt.livro_id = l.id
				LEFT JOIN tags t ON t.id = lt.tag_id
				{clausula_where}
				GROUP BY l.id
				ORDER BY l.titulo ASC
			"""
			cursor.execute(consulta, tuple(parametros))
			resultados = []
			for linha in cursor.fetchall():
				item = dict(linha)
				item["tags"] = sorted(list(item["tags"])) if item.get("tags") else []
				resultados.append(item)
			return resultados

def obter_livro_por_id(livro_id):
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute(
				"""
				SELECT
					l.*,
					COALESCE(
						ARRAY_AGG(DISTINCT t.nome) FILTER (WHERE t.nome IS NOT NULL),
						'{}'
					) AS tags
				FROM livros l
				LEFT JOIN livro_tags lt ON lt.livro_id = l.id
				LEFT JOIN tags t ON t.id = lt.tag_id
				WHERE l.id = %s
				GROUP BY l.id
				""",
				(livro_id,)
			)
			registro = cursor.fetchone()
			if not registro:
				return None

			livro = dict(registro)
			livro["tags"] = sorted(list(livro["tags"])) if livro.get("tags") else []

			cursor.execute(
				"""
				SELECT
					r.id,
					r.usuario_id,
					u.nome AS usuario_nome,
					u.usuario AS usuario_login,
					r.nota,
					r.texto,
					r.criado_em
				FROM resenhas r
				JOIN usuarios u ON u.id = r.usuario_id
				WHERE r.livro_id = %s
				ORDER BY r.criado_em DESC
				""",
				(livro_id,)
			)
			livro["resenhas"] = [dict(resenha) for resenha in cursor.fetchall()]
			return livro

def criar_livro(titulo, autor, isbn_13=None, isbn_10=None, editora=None, ano_publicacao=None, paginas=None, sinopse=None, capa_url=None, formato="Físico", tags_lista=None):
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute(
				"""
				INSERT INTO livros (
					titulo, autor, isbn_13, isbn_10, editora,
					ano_publicacao, paginas, sinopse, capa_url, formato, disponivel
				)
				VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE)
				RETURNING id
				""",
				(
					titulo.strip(),
					autor.strip() if autor else "Autor Desconhecido",
					isbn_13.strip() if isbn_13 else None,
					isbn_10.strip() if isbn_10 else None,
					editora.strip() if editora else None,
					int(ano_publicacao) if ano_publicacao else None,
					int(paginas) if paginas else None,
					sinopse.strip() if sinopse else None,
					capa_url.strip() if capa_url else None,
					formato.strip() if formato else "Físico"
				)
			)
			livro_id = cursor.fetchone()["id"]
			_sincronizar_tags_livro(cursor, livro_id, tags_lista)
	return obter_livro_por_id(livro_id)

def atualizar_livro(livro_id, titulo, autor, isbn_13=None, isbn_10=None, editora=None, ano_publicacao=None, paginas=None, sinopse=None, capa_url=None, formato="Físico", tags_lista=None):
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute(
				"""
				UPDATE livros
				SET
					titulo = %s,
					autor = %s,
					isbn_13 = %s,
					isbn_10 = %s,
					editora = %s,
					ano_publicacao = %s,
					paginas = %s,
					sinopse = %s,
					capa_url = %s,
					formato = %s
				WHERE id = %s
				RETURNING id
				""",
				(
					titulo.strip(),
					autor.strip() if autor else "Autor Desconhecido",
					isbn_13.strip() if isbn_13 else None,
					isbn_10.strip() if isbn_10 else None,
					editora.strip() if editora else None,
					int(ano_publicacao) if ano_publicacao else None,
					int(paginas) if paginas else None,
					sinopse.strip() if sinopse else None,
					capa_url.strip() if capa_url else None,
					formato.strip() if formato else "Físico",
					livro_id
				)
			)
			atualizado = cursor.fetchone()
			if not atualizado:
				return None

			if tags_lista is not None:
				_sincronizar_tags_livro(cursor, livro_id, tags_lista)
	return obter_livro_por_id(livro_id)

def excluir_livro(livro_id):
	with obter_conexao() as conexao:
		with conexao.cursor() as cursor:
			cursor.execute("DELETE FROM livros WHERE id = %s", (livro_id,))
			return cursor.rowcount > 0

def listar_tags_populares(limite=30):
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute(
				"""
				SELECT t.id, t.nome, COUNT(lt.livro_id) AS total_livros
				FROM tags t
				JOIN livro_tags lt ON lt.tag_id = t.id
				GROUP BY t.id, t.nome
				ORDER BY total_livros DESC, t.nome ASC
				LIMIT %s
				""",
				(limite,)
			)
			return [dict(linha) for linha in cursor.fetchall()]
