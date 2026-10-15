import hashlib
import hmac
import os
import time

ITERACOES_HASH = 200_000
VALIDADE_TOKEN_SEGUNDOS = 60 * 60 * 24 * 30


def calcular_hash(senha: str, sal_hex: str) -> str:
	return hashlib.pbkdf2_hmac("sha256", senha.encode(), bytes.fromhex(sal_hex), ITERACOES_HASH).hex()


def gerar_hash_senha(senha: str) -> str:
	sal_hex = os.urandom(16).hex()
	return f"{sal_hex}${calcular_hash(senha, sal_hex)}"


def verificar_senha(senha: str, senha_hash: str) -> bool:
	sal_hex, hash_esperado = senha_hash.split("$")
	return hmac.compare_digest(calcular_hash(senha, sal_hex), hash_esperado)


def assinar(conteudo: str) -> str:
	chave = os.environ["SECRET_KEY"].encode()
	return hmac.new(chave, conteudo.encode(), hashlib.sha256).hexdigest()


def criar_token(id_usuario: int, expira_em: int | None = None) -> str:
	if expira_em is None:
		expira_em = int(time.time()) + VALIDADE_TOKEN_SEGUNDOS
	conteudo = f"{id_usuario}.{expira_em}"
	return f"{conteudo}.{assinar(conteudo)}"


def validar_token(token: str) -> int | None:
	partes = token.split(".")
	if len(partes) != 3:
		return None
	id_usuario, expira_em, assinatura = partes
	if not (id_usuario.isdigit() and expira_em.isdigit()):
		return None
	if not hmac.compare_digest(assinar(f"{id_usuario}.{expira_em}"), assinatura):
		return None
	if int(expira_em) < time.time():
		return None
	return int(id_usuario)
