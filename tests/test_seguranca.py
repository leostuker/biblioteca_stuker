import time

from backend.seguranca import criar_token, gerar_hash_senha, validar_token, verificar_senha


def test_senha_correta_e_verificada():
	senha_hash = gerar_hash_senha("minha-senha")
	assert verificar_senha("minha-senha", senha_hash)


def test_senha_errada_e_rejeitada():
	senha_hash = gerar_hash_senha("minha-senha")
	assert not verificar_senha("outra-senha", senha_hash)


def test_mesma_senha_gera_hashes_diferentes():
	assert gerar_hash_senha("minha-senha") != gerar_hash_senha("minha-senha")


def test_token_valido_devolve_id_do_usuario():
	assert validar_token(criar_token(42)) == 42


def test_token_adulterado_e_rejeitado():
	token = criar_token(42)
	id_usuario, expira_em, assinatura = token.split(".")
	assert validar_token(f"1.{expira_em}.{assinatura}") is None


def test_token_expirado_e_rejeitado():
	token = criar_token(42, expira_em=int(time.time()) - 10)
	assert validar_token(token) is None


def test_token_malformado_e_rejeitado():
	assert validar_token("lixo") is None
