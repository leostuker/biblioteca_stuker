import re
import json
import socket
import struct
import urllib.request
import urllib.error
from typing import Optional, Tuple, Dict, Any
from pymarc import MARCReader

_FBN_FALHAS_CONSECUTIVAS = 0
_FBN_LIMITE_FALHAS = 3

def normalizar_isbn(isbn_bruto: str) -> Optional[str]:
	if not isbn_bruto:
		return None
	limpo = re.sub(r"[^0-9Xx]", "", str(isbn_bruto)).upper()
	if len(limpo) == 10:
		if not limpo[:9].isdigit():
			return None
		soma = 0
		for i in range(9):
			soma += int(limpo[i]) * (10 - i)
		ultimo = 10 if limpo[9] == "X" else int(limpo[9])
		soma += ultimo
		if soma % 11 != 0:
			return None
		base13 = "978" + limpo[:9]
		soma13 = sum((1 if i % 2 == 0 else 3) * int(base13[i]) for i in range(12))
		digito13 = (10 - (soma13 % 10)) % 10
		return base13 + str(digito13)
	elif len(limpo) == 13:
		if not limpo.isdigit():
			return None
		if not (limpo.startswith("978") or limpo.startswith("979")):
			return None
		soma13 = sum((1 if i % 2 == 0 else 3) * int(limpo[i]) for i in range(12))
		digito13 = (10 - (soma13 % 10)) % 10
		if digito13 != int(limpo[12]):
			return None
		return limpo
	return None

def _limpar_isbd(texto: Optional[str]) -> str:
	if not texto:
		return ""
	texto_limpo = re.sub(r"\s*[/;:=.,]+\s*$", "", str(texto).strip())
	return re.sub(r"^\s*\[|\]\s*$", "", texto_limpo).strip()

def _extrair_ano(texto: Optional[str]) -> Optional[int]:
	if not texto:
		return None
	match = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", str(texto))
	return int(match.group(1)) if match else None

def _extrair_paginas(texto: Optional[str]) -> Optional[int]:
	if not texto:
		return None
	match = re.search(r"(\d+)\s*(?:p\.|p\b|págs|paginas|páginas|pages|f\.)", str(texto), re.IGNORECASE)
	if match:
		return int(match.group(1))
	match_num = re.search(r"\b(\d+)\b", str(texto))
	return int(match_num.group(1)) if match_num else None

def consultar_openlibrary(isbn_13: str) -> Optional[Dict[str, Any]]:
	url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{isbn_13}&format=json&jscmd=data"
	req = urllib.request.Request(url, headers={"User-Agent": "BibliotecaStuker/1.0"})
	try:
		with urllib.request.urlopen(req, timeout=2.0) as resp:
			if resp.status != 200:
				return None
			dados = json.loads(resp.read().decode("utf-8"))
			chave = f"ISBN:{isbn_13}"
			if chave not in dados:
				return None
			info = dados[chave]
			titulo = _limpar_isbd(info.get("title", ""))
			subtitulo = _limpar_isbd(info.get("subtitle", ""))
			titulo_completo = f"{titulo}: {subtitulo}" if subtitulo else titulo
			if not titulo_completo:
				return None
			autores = [_limpar_isbd(a.get("name", "")) for a in info.get("authors", []) if a.get("name")]
			editoras = [_limpar_isbd(p.get("name", "")) for p in info.get("publishers", []) if p.get("name")]
			assuntos = [_limpar_isbd(s.get("name", "")) for s in info.get("subjects", [])[:5] if s.get("name")]
			ano = _extrair_ano(info.get("publish_date", ""))
			paginas = info.get("number_of_pages")
			capa = info.get("cover", {}).get("large") or info.get("cover", {}).get("medium") or ""
			return {
				"isbn": isbn_13,
				"titulo": titulo_completo,
				"autor": ", ".join(autores),
				"editora": editoras[0] if editoras else "",
				"ano_publicacao": ano,
				"paginas": int(paginas) if paginas else None,
				"assunto": ", ".join(assuntos),
				"capa_url": capa,
				"sinopse": ""
			}
	except Exception:
		return None

def consultar_googlebooks(isbn_13: str) -> Optional[Dict[str, Any]]:
	url = f"https://www.googleapis.com/books/v1/volumes?q=isbn:{isbn_13}"
	req = urllib.request.Request(url, headers={"User-Agent": "BibliotecaStuker/1.0"})
	try:
		with urllib.request.urlopen(req, timeout=2.5) as resp:
			if resp.status != 200:
				return None
			dados = json.loads(resp.read().decode("utf-8"))
			items = dados.get("items", [])
			if not items:
				return None
			volume_valido = None
			for item in items:
				vol = item.get("volumeInfo", {})
				identificadores = vol.get("industryIdentifiers", [])
				for ident in identificadores:
					valor_id = normalizar_isbn(ident.get("identifier", ""))
					if valor_id == isbn_13:
						volume_valido = vol
						break
				if volume_valido:
					break
			if not volume_valido:
				return None
			titulo = _limpar_isbd(volume_valido.get("title", ""))
			subtitulo = _limpar_isbd(volume_valido.get("subtitle", ""))
			titulo_completo = f"{titulo}: {subtitulo}" if subtitulo else titulo
			if not titulo_completo:
				return None
			autores = [_limpar_isbd(a) for a in volume_valido.get("authors", []) if a]
			editora = _limpar_isbd(volume_valido.get("publisher", ""))
			ano = _extrair_ano(volume_valido.get("publishedDate", ""))
			paginas = volume_valido.get("pageCount")
			categorias = [_limpar_isbd(c) for c in volume_valido.get("categories", []) if c]
			capa = volume_valido.get("imageLinks", {}).get("thumbnail", "")
			if capa.startswith("http://"):
				capa = "https://" + capa[7:]
			sinopse = volume_valido.get("description", "").strip()
			return {
				"isbn": isbn_13,
				"titulo": titulo_completo,
				"autor": ", ".join(autores),
				"editora": editora,
				"ano_publicacao": ano,
				"paginas": int(paginas) if paginas else None,
				"assunto": ", ".join(categorias),
				"capa_url": capa,
				"sinopse": sinopse
			}
	except Exception:
		return None

def _ber_len(tamanho: int) -> bytes:
	if tamanho < 128:
		return bytes([tamanho])
	hex_str = f"{tamanho:x}"
	if len(hex_str) % 2 != 0:
		hex_str = "0" + hex_str
	b_len = bytes.fromhex(hex_str)
	return bytes([0x80 | len(b_len)]) + b_len

def _ber_tag(tag: int, conteudo: bytes) -> bytes:
	if tag <= 0xFF:
		b_tag = bytes([tag])
	else:
		b_tag = struct.pack(">H", tag)
	return b_tag + _ber_len(len(conteudo)) + conteudo

def _construir_init_apdu() -> bytes:
	proto_ver = _ber_tag(0x83, b"\x05\xd0")
	options = _ber_tag(0x84, b"\x02\x60\x00")
	pref_msg = _ber_tag(0x85, b"\x01\x00\x00")
	max_rec = _ber_tag(0x86, b"\x01\x00\x00")
	corpo = proto_ver + options + pref_msg + max_rec
	return _ber_tag(0xBF14, corpo)

def _construir_search_apdu(isbn_13: str, nome_base: str = "acervo") -> bytes:
	small_set = _ber_tag(0x8E, b"\x00")
	large_set = _ber_tag(0x8F, b"\x01")
	medium_set = _ber_tag(0x90, b"\x00")
	replace_ind = _ber_tag(0x91, b"\x01")
	result_name = _ber_tag(0x92, b"default")
	db_names = _ber_tag(0xB3, _ber_tag(0x80, nome_base.encode("ascii")))
	oid_bib1 = b"\x2a\x86\x48\xce\x13\x03\x01"
	attr_type = _ber_tag(0x80, b"\x01")
	attr_val = _ber_tag(0x81, b"\x07")
	attr_elem = _ber_tag(0x30, attr_type + attr_val)
	attr_list = _ber_tag(0xAC, attr_elem)
	term = _ber_tag(0xAD, isbn_13.encode("ascii"))
	apt = _ber_tag(0xA2, attr_list + term)
	operand = _ber_tag(0xA0, apt)
	rpn_struct = _ber_tag(0xA0, operand)
	rpn_query = _ber_tag(0xA1, _ber_tag(0x06, oid_bib1) + rpn_struct)
	query = _ber_tag(0x95, rpn_query)
	corpo = small_set + large_set + medium_set + replace_ind + result_name + db_names + query
	return _ber_tag(0xBF16, corpo)

def _construir_present_apdu() -> bytes:
	result_id = _ber_tag(0x92, b"default")
	start_pt = _ber_tag(0x9E, b"\x01")
	num_recs = _ber_tag(0x9D, b"\x01")
	oid_usmarc = b"\x2a\x86\x48\xce\x13\x05\x0a"
	pref_syntax = _ber_tag(0xA7, _ber_tag(0x06, oid_usmarc))
	corpo = result_id + start_pt + num_recs + pref_syntax
	return _ber_tag(0xBF18, corpo)

def _extrair_marc_binario(resposta: bytes) -> Optional[bytes]:
	padrao = re.search(rb"(\d{5}[a-zA-Z0-9\s]{3}[a-zA-Z\s]{2}22\d{5})", resposta)
	if not padrao:
		return None
	inicio = padrao.start()
	try:
		tamanho = int(resposta[inicio:inicio + 5].decode("ascii"))
		fim = inicio + tamanho
		if fim <= len(resposta):
			return resposta[inicio:fim]
	except Exception:
		return None
	return None

def _parsear_registro_marc(dados_marc: bytes, isbn_13: str) -> Optional[Dict[str, Any]]:
	leitor = MARCReader(dados_marc, to_unicode=True, force_utf8=True)
	for registro in leitor:
		if registro is None:
			continue
		titulo_partes = []
		f245 = registro.get_fields("245")
		if f245:
			a = _limpar_isbd(f245[0].get("a", ""))
			b = _limpar_isbd(f245[0].get("b", ""))
			if a:
				titulo_partes.append(a)
			if b:
				titulo_partes.append(b)
		titulo_completo = ": ".join(titulo_partes)
		if not titulo_completo:
			continue
		autores = []
		for tag_autor in ("100", "700"):
			for campo in registro.get_fields(tag_autor):
				nome = _limpar_isbd(campo.get("a", ""))
				if nome and nome not in autores:
					autores.append(nome)
		editora = ""
		ano = None
		for tag_pub in ("260", "264"):
			campos_pub = registro.get_fields(tag_pub)
			if campos_pub:
				b_pub = _limpar_isbd(campos_pub[0].get("b", ""))
				c_pub = campos_pub[0].get("c", "")
				if b_pub and not editora:
					editora = b_pub
				if c_pub and not ano:
					ano = _extrair_ano(c_pub)
		paginas = None
		f300 = registro.get_fields("300")
		if f300:
			paginas = _extrair_paginas(f300[0].get("a", ""))
		assuntos = []
		for campo_assunto in registro.get_fields("650"):
			termo = _limpar_isbd(campo_assunto.get("a", ""))
			if termo and termo not in assuntos:
				assuntos.append(termo)
		return {
			"isbn": isbn_13,
			"titulo": titulo_completo,
			"autor": ", ".join(autores),
			"editora": editora,
			"ano_publicacao": ano,
			"paginas": paginas,
			"assunto": ", ".join(assuntos[:5]),
			"capa_url": "",
			"sinopse": ""
		}
	return None

def _receber_socket(sock: socket.socket) -> bytes:
	chunks = []
	while True:
		try:
			dados = sock.recv(4096)
			if not dados:
				break
			chunks.append(dados)
			if len(dados) < 4096:
				break
		except socket.timeout:
			break
	return b"".join(chunks)

def consultar_fbn_z3950(isbn_13: str) -> Optional[Dict[str, Any]]:
	global _FBN_FALHAS_CONSECUTIVAS
	if _FBN_FALHAS_CONSECUTIVAS >= _FBN_LIMITE_FALHAS:
		return None
	host = "z3950.bn.gov.br"
	portas = (210, 2109)
	sock_conectado = None
	for porta in portas:
		try:
			sock = socket.create_connection((host, porta), timeout=1.5)
			sock.settimeout(2.0)
			sock_conectado = sock
			break
		except Exception:
			continue
	if not sock_conectado:
		_FBN_FALHAS_CONSECUTIVAS += 1
		return None
	try:
		with sock_conectado:
			sock_conectado.sendall(_construir_init_apdu())
			resp_init = _receber_socket(sock_conectado)
			if not resp_init:
				_FBN_FALHAS_CONSECUTIVAS += 1
				return None
			for base in ("acervo", "Default"):
				sock_conectado.sendall(_construir_search_apdu(isbn_13, base))
				resp_search = _receber_socket(sock_conectado)
				if not resp_search:
					continue
				marc_direto = _extrair_marc_binario(resp_search)
				if marc_direto:
					_FBN_FALHAS_CONSECUTIVAS = 0
					return _parsear_registro_marc(marc_direto, isbn_13)
				sock_conectado.sendall(_construir_present_apdu())
				resp_present = _receber_socket(sock_conectado)
				marc_present = _extrair_marc_binario(resp_present)
				if marc_present:
					_FBN_FALHAS_CONSECUTIVAS = 0
					return _parsear_registro_marc(marc_present, isbn_13)
			_FBN_FALHAS_CONSECUTIVAS = 0
			return None
	except Exception:
		_FBN_FALHAS_CONSECUTIVAS += 1
		return None

def resetar_circuit_breaker_fbn() -> None:
	global _FBN_FALHAS_CONSECUTIVAS
	_FBN_FALHAS_CONSECUTIVAS = 0

def buscar_dados_isbn(isbn_bruto: str) -> Tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
	isbn_13 = normalizar_isbn(isbn_bruto)
	if not isbn_13:
		return None, None, "ISBN inválido. Verifique os dígitos informados."
	provedores = [
		("Open Library", consultar_openlibrary),
		("Google Books", consultar_googlebooks),
		("Fundação Biblioteca Nacional (Z39.50)", consultar_fbn_z3950),
	]
	for nome_provedor, funcao_consulta in provedores:
		resultado = funcao_consulta(isbn_13)
		if resultado and resultado.get("titulo"):
			return resultado, nome_provedor, None
	return (
		{"isbn": isbn_13},
		None,
		f"Nenhum registro encontrado nas bases externas para o ISBN {isbn_13}."
	)
