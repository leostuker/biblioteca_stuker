from psycopg2.extras import RealDictCursor
from backend.bd import obter_conexao

def registrar_emprestimo(livro_id, nome_destinatario, contato=None, data_previsao=None, observacoes=None, usuario_id=None):
	if not nome_destinatario or not nome_destinatario.strip():
		raise ValueError("O nome do destinatário é obrigatório")

	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute("SELECT disponivel FROM livros WHERE id = %s FOR UPDATE", (livro_id,))
			livro = cursor.fetchone()
			if not livro:
				raise ValueError("Livro não encontrado")
			if not livro["disponivel"]:
				raise ValueError("Este livro já está emprestado")

			cursor.execute(
				"""
				INSERT INTO emprestimos (
					livro_id, usuario_id, nome_destinatario, contato_destinatario,
					data_emprestimo, data_devolucao_prevista, observacoes, status
				)
				VALUES (%s, %s, %s, %s, CURRENT_DATE, %s, %s, 'ativo')
				RETURNING *
				""",
				(
					livro_id,
					usuario_id if usuario_id else None,
					nome_destinatario.strip(),
					contato.strip() if contato else None,
					data_previsao if data_previsao else None,
					observacoes.strip() if observacoes else None
				)
			)
			novo_emprestimo = cursor.fetchone()

			cursor.execute(
				"UPDATE livros SET disponivel = FALSE WHERE id = %s",
				(livro_id,)
			)
			return dict(novo_emprestimo)

def registrar_devolucao(emprestimo_id):
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute(
				"""
				UPDATE emprestimos
				SET data_devolucao_real = CURRENT_DATE, status = 'devolvido'
				WHERE id = %s AND data_devolucao_real IS NULL
				RETURNING *
				""",
				(emprestimo_id,)
			)
			emprestimo = cursor.fetchone()
			if not emprestimo:
				return None

			cursor.execute(
				"UPDATE livros SET disponivel = TRUE WHERE id = %s",
				(emprestimo["livro_id"],)
			)
			return dict(emprestimo)

def listar_emprestimos(apenas_ativos=False):
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			filtro = "WHERE e.data_devolucao_real IS NULL" if apenas_ativos else ""
			consulta = f"""
				SELECT
					e.*,
					l.titulo AS livro_titulo,
					l.autor AS livro_autor,
					l.capa_url AS livro_capa_url,
					u.nome AS usuario_cadastrado_nome,
					CASE
						WHEN e.data_devolucao_real IS NULL AND e.data_devolucao_prevista IS NOT NULL AND e.data_devolucao_prevista < CURRENT_DATE
						THEN TRUE
						ELSE FALSE
					END AS atrasado
				FROM emprestimos e
				JOIN livros l ON l.id = e.livro_id
				LEFT JOIN usuarios u ON u.id = e.usuario_id
				{filtro}
				ORDER BY
					e.data_devolucao_real ASC NULLS FIRST,
					e.data_emprestimo DESC
			"""
			cursor.execute(consulta)
			return [dict(linha) for linha in cursor.fetchall()]
