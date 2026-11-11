import json
from unittest.mock import patch, MagicMock
import pytest
from pymarc import Record, Field, Subfield
from backend.servicos import isbn_servico
from backend.servicos.isbn_servico import (
	normalizar_isbn,
	consultar_openlibrary,
	consultar_googlebooks,
	consultar_fbn_z3950,
	buscar_dados_isbn,
	resetar_circuit_breaker_fbn,
	_parsear_registro_marc
)

def test_normalizar_isbn_10_valido():
	assert normalizar_isbn("85-359-0277-5") == "9788535902778"
	assert normalizar_isbn("8535902775") == "9788535902778"

def test_normalizar_isbn_10_com_x():
	assert normalizar_isbn("0-8044-2957-X") == "9780804429573"

def test_normalizar_isbn_10_invalido():
	assert normalizar_isbn("85-359-0277-0") is None

def test_normalizar_isbn_13_valido():
	assert normalizar_isbn("978-85-359-0277-8") == "9788535902778"
	assert normalizar_isbn("979-10-90636-07-1") == "9791090636071"

def test_normalizar_isbn_13_invalido():
	assert normalizar_isbn("978-85-359-0277-0") is None
	assert normalizar_isbn("1234567890123") is None
	assert normalizar_isbn("") is None
	assert normalizar_isbn(None) is None

def test_parsing_openlibrary():
	payload = {
		"ISBN:9788535902778": {
			"title": "Cidade de Deus",
			"subtitle": "romance",
			"authors": [{"name": "Paulo Lins"}],
			"publishers": [{"name": "Companhia das Letras"}],
			"publish_date": "2002",
			"number_of_pages": 403,
			"subjects": [{"name": "Ficção brasileira"}],
			"cover": {"large": "https://covers.openlibrary.org/b/id/123-L.jpg"}
		}
	}
	resposta_mock = MagicMock()
	resposta_mock.status = 200
	resposta_mock.read.return_value = json.dumps(payload).encode("utf-8")
	resposta_mock.__enter__.return_value = resposta_mock

	with patch("urllib.request.urlopen", return_value=resposta_mock):
		dados = consultar_openlibrary("9788535902778")
		assert dados is not None
		assert dados["titulo"] == "Cidade de Deus: romance"
		assert dados["autor"] == "Paulo Lins"
		assert dados["editora"] == "Companhia das Letras"
		assert dados["ano_publicacao"] == 2002
		assert dados["paginas"] == 403

def test_parsing_googlebooks_valida_identificador():
	payload = {
		"items": [
			{
				"volumeInfo": {
					"title": "Outro Livro",
					"industryIdentifiers": [{"type": "ISBN_13", "identifier": "9780000000000"}]
				}
			},
			{
				"volumeInfo": {
					"title": "Dom Casmurro",
					"authors": ["Machado de Assis"],
					"publisher": "Penguin",
					"publishedDate": "2016-05-10",
					"pageCount": 320,
					"categories": ["Literatura Brasileira"],
					"industryIdentifiers": [{"type": "ISBN_13", "identifier": "9788535902778"}]
				}
			}
		]
	}
	resposta_mock = MagicMock()
	resposta_mock.status = 200
	resposta_mock.read.return_value = json.dumps(payload).encode("utf-8")
	resposta_mock.__enter__.return_value = resposta_mock

	with patch("urllib.request.urlopen", return_value=resposta_mock):
		dados = consultar_googlebooks("9788535902778")
		assert dados is not None
		assert dados["titulo"] == "Dom Casmurro"
		assert dados["autor"] == "Machado de Assis"
		assert dados["ano_publicacao"] == 2016
		assert dados["paginas"] == 320

def test_parsing_marc_fbn_com_limpeza_isbd():
	reg = Record(force_utf8=True)
	reg.add_field(Field(
		tag="100",
		indicators=["1", " "],
		subfields=[Subfield(code="a", value="Assis, Machado de,")]
	))
	reg.add_field(Field(
		tag="245",
		indicators=["1", "0"],
		subfields=[
			Subfield(code="a", value="Memórias póstumas de Brás Cubas :"),
			Subfield(code="b", value="texto integral /")
		]
	))
	reg.add_field(Field(
		tag="260",
		indicators=[" ", " "],
		subfields=[
			Subfield(code="b", value="Editora Garnier,"),
			Subfield(code="c", value="[1998].")
		]
	))
	reg.add_field(Field(
		tag="300",
		indicators=[" ", " "],
		subfields=[Subfield(code="a", value="248 p. :")]
	))
	reg.add_field(Field(
		tag="650",
		indicators=[" ", "4"],
		subfields=[Subfield(code="a", value="Romance brasileiro.")]
	))

	dados = _parsear_registro_marc(reg.as_marc(), "9788535902778")
	assert dados is not None
	assert dados["titulo"] == "Memórias póstumas de Brás Cubas: texto integral"
	assert dados["autor"] == "Assis, Machado de"
	assert dados["editora"] == "Editora Garnier"
	assert dados["ano_publicacao"] == 1998
	assert dados["paginas"] == 248

def test_fallback_cascata_provedores():
	dados_google = {
		"isbn": "9788535902778",
		"titulo": "Vidas Secas",
		"autor": "Graciliano Ramos",
		"editora": "Record",
		"ano_publicacao": 2019,
		"paginas": 176,
		"assunto": "Ficção",
		"capa_url": "",
		"sinopse": ""
	}
	with patch.object(isbn_servico, "consultar_openlibrary", return_value=None) as mock_ol, \
		patch.object(isbn_servico, "consultar_googlebooks", return_value=dados_google) as mock_gb, \
		patch.object(isbn_servico, "consultar_fbn_z3950", return_value=None) as mock_fbn:

		resultado, provedor, erro = buscar_dados_isbn("85-359-0277-5")
		assert erro is None
		assert provedor == "Google Books"
		assert resultado["titulo"] == "Vidas Secas"
		mock_ol.assert_called_once_with("9788535902778")
		mock_gb.assert_called_once_with("9788535902778")
		mock_fbn.assert_not_called()

def test_circuit_breaker_fbn():
	resetar_circuit_breaker_fbn()
	with patch("socket.create_connection", side_effect=OSError("Timeout")) as mock_conn:
		assert consultar_fbn_z3950("9788535902778") is None
		assert consultar_fbn_z3950("9788535902778") is None
		assert consultar_fbn_z3950("9788535902778") is None
		chamadas_apos_3_falhas = mock_conn.call_count
		assert consultar_fbn_z3950("9788535902778") is None
		assert mock_conn.call_count == chamadas_apos_3_falhas
	resetar_circuit_breaker_fbn()
