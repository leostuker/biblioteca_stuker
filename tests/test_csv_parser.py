import pytest
from backend.servicos.importador_csv import _extrair_ano, _extrair_paginas, _limpar_isbn, _extrair_tags

@pytest.mark.parametrize("entrada,esperado", [
	("2023", 2023),
	("1998-05-14", 1998),
	("2021/11/30", 2021),
	("Publicado em 1889 na Inglaterra", 1889),
	("", None),
	(None, None),
	("Data desconhecida", None),
])
def test_extrair_ano(entrada, esperado):
	assert _extrair_ano(entrada) == esperado

@pytest.mark.parametrize("entrada,esperado", [
	("350", 350),
	(420, 420),
	("280 páginas", 280),
	("aprox. 150 p.", 150),
	("", None),
	(None, None),
	("N/A", None),
	("Sem número", None),
])
def test_extrair_paginas(entrada, esperado):
	assert _extrair_paginas(entrada) == esperado

@pytest.mark.parametrize("entrada,esperado", [
	("978-85-359-0277-8", "9788535902778"),
	("8535902775", "8535902775"),
	("0-306-40615-X", "030640615X"),
	("0-306-40615-x", "030640615X"),
	("=\"9788535902778\"", "9788535902778"),
	("ISBN: 978 85 359 0277 8", "9788535902778"),
	("", None),
	(None, None),
])
def test_limpar_isbn(entrada, esperado):
	resultado = _limpar_isbn(entrada)
	if esperado is None:
		assert not resultado
	else:
		assert resultado == esperado

@pytest.mark.parametrize("entrada,esperado", [
	("Ficção, Fantasia, Aventura", ["ficção", "fantasia", "aventura"]),
	("História; Biografia; Política", ["história", "biografia", "política"]),
	("  Terror ,  Suspense  , ", ["terror", "suspense"]),
	("Ciência", ["ciência"]),
	("", []),
	(None, []),
])
def test_extrair_tags(entrada, esperado):
	assert _extrair_tags(entrada) == esperado
