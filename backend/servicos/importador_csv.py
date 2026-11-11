import os
import re
import csv
from psycopg2.extras import RealDictCursor
from backend.bd import obter_conexao

PADRAO_ANO = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")

def _limpar_texto(valor):
	if valor is None:
		return None
	texto = str(valor).strip()
	return texto if texto else None

def _limpar_isbn(valor):
	texto = _limpar_texto(valor)
	if not texto:
		return None
	limpo = re.sub(r"[^0-9Xx]", "", texto).upper()
	return limpo if limpo else None

def _extrair_ano(valor):
	texto = _limpar_texto(valor)
	if not texto:
		return None
	correspondencia = PADRAO_ANO.search(texto)
	if correspondencia:
		return int(correspondencia.group(1))
	return None

def _extrair_paginas(valor):
	texto = _limpar_texto(valor)
	if not texto:
		return None
	digitos = re.sub(r"[^\d]", "", texto)
	if digitos:
		numero = int(digitos)
		return numero if numero > 0 else None
	return None

def _extrair_tags(valor):
	texto = _limpar_texto(valor)
	if not texto:
		return []
	partes = [parte.strip().lower() for parte in re.split(r"[,;]", texto)]
	return [p for p in partes if p]

def importar_libib_csv(caminho_csv):
	if not caminho_csv or not os.path.exists(caminho_csv):
		return 0

	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute("SELECT COUNT(*) AS total FROM livros")
			contagem = cursor.fetchone()["total"]
			if contagem > 0:
				return 0

			livros_importados = 0
			cache_tags = {}

			with open(caminho_csv, mode="r", encoding="utf-8-sig", newline="") as arquivo:
				leitor = csv.DictReader(arquivo)
				for linha in leitor:
					tipo_item = _limpar_texto(linha.get("item_type"))
					if tipo_item and tipo_item.lower() not in ("book", "livro"):
						continue

					titulo = _limpar_texto(linha.get("title"))
					if not titulo:
						continue

					autor = _limpar_texto(linha.get("creators")) or "Autor Desconhecido"
					isbn_13 = _limpar_isbn(linha.get("ean_isbn13"))
					isbn_10 = _limpar_isbn(linha.get("upc_isbn10"))
					editora = _limpar_texto(linha.get("publisher"))
					ano_publicacao = _extrair_ano(linha.get("publish_date"))
					paginas = _extrair_paginas(linha.get("length"))
					sinopse = _limpar_texto(linha.get("description"))
					tags_lista = _extrair_tags(linha.get("tags"))

					cursor.execute(
						"""
						INSERT INTO livros (
							titulo, autor, isbn_13, isbn_10, editora,
							ano_publicacao, paginas, sinopse, formato, disponivel
						)
						VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'Físico', TRUE)
						RETURNING id
						""",
						(
							titulo,
							autor,
							isbn_13,
							isbn_10,
							editora,
							ano_publicacao,
							paginas,
							sinopse
						)
					)
					livro_id = cursor.fetchone()["id"]
					livros_importados += 1

					for nome_tag in set(tags_lista):
						if nome_tag in cache_tags:
							tag_id = cache_tags[nome_tag]
						else:
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
							cache_tags[nome_tag] = tag_id

						cursor.execute(
							"""
							INSERT INTO livro_tags (livro_id, tag_id)
							VALUES (%s, %s)
							ON CONFLICT DO NOTHING
							""",
							(livro_id, tag_id)
						)

			return livros_importados
