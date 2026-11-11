import pytest
from backend.seguranca import gerar_hash_senha, verificar_senha, criar_token_sessao, validar_token_sessao

def test_gerar_e_verificar_senha_correta():
	senha = "SenhaForteBiblioteca@2026"
	hash_gerado = gerar_hash_senha(senha)
	assert hash_gerado != senha
	assert verificar_senha(senha, hash_gerado) is True

def test_verificar_senha_errada():
	senha = "SenhaForteBiblioteca@2026"
	hash_gerado = gerar_hash_senha(senha)
	assert verificar_senha("SenhaIncorreta123", hash_gerado) is False

def test_criar_e_validar_token_sessao_valido():
	usuario_id = 42
	token = criar_token_sessao(usuario_id)
	assert isinstance(token, str)
	assert validar_token_sessao(token) == usuario_id

def test_validar_token_sessao_adulterado():
	usuario_id = 42
	token = criar_token_sessao(usuario_id)
	partes = token.split(".")
	if len(partes) > 1:
		token_adulterado = f"{partes[0]}.assinatura_falsa_invalida"
	else:
		token_adulterado = f"{token}adulterado"
	assert validar_token_sessao(token_adulterado) is None
	assert validar_token_sessao("token.totalmente.invalido") is None
	assert validar_token_sessao("") is None
