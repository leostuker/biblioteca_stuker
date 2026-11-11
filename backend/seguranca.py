import os
import hashlib
import hmac
from fastapi import Request, HTTPException, status, Depends
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from psycopg2.extras import RealDictCursor
from backend.bd import obter_conexao

SECRET_KEY = os.environ.get("SECRET_KEY", "chave_secreta_biblioteca_stuker_1998")
NOME_COOKIE = "sessao_stuker"
EXPIRACAO_SEGUNDOS = 86400 * 14

serializador = URLSafeTimedSerializer(SECRET_KEY)

def gerar_hash_senha(senha: str) -> str:
	salt = os.urandom(16)
	chave = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), salt, 100000)
	return f"{salt.hex()}${chave.hex()}"

def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
	try:
		salt_hex, chave_hex = senha_hash.split("$")
		salt = bytes.fromhex(salt_hex)
		chave_esperada = bytes.fromhex(chave_hex)
		chave_calculada = hashlib.pbkdf2_hmac("sha256", senha_plana.encode("utf-8"), salt, 100000)
		return hmac.compare_digest(chave_calculada, chave_esperada)
	except Exception:
		return False

def criar_token_sessao(usuario_id: int) -> str:
	return serializador.dumps({"usuario_id": usuario_id})

def validar_token_sessao(token: str) -> int | None:
	try:
		dados = serializador.loads(token, max_age=EXPIRACAO_SEGUNDOS)
		return dados.get("usuario_id")
	except (BadSignature, SignatureExpired):
		return None

def obter_usuario_opcional(request: Request) -> dict | None:
	token = request.cookies.get(NOME_COOKIE)
	if not token:
		return None
	usuario_id = validar_token_sessao(token)
	if not usuario_id:
		return None
	with obter_conexao() as conexao:
		with conexao.cursor(cursor_factory=RealDictCursor) as cursor:
			cursor.execute(
				"SELECT id, usuario, nome, email, is_admin, criado_em FROM usuarios WHERE id = %s",
				(usuario_id,)
			)
			usuario = cursor.fetchone()
			return dict(usuario) if usuario else None

def obter_usuario_logado(usuario: dict | None = Depends(obter_usuario_opcional)) -> dict:
	if not usuario:
		raise HTTPException(
			status_code=status.HTTP_401_UNAUTHORIZED,
			detail="Usuário não autenticado"
		)
	return usuario

def exigir_admin(usuario: dict = Depends(obter_usuario_logado)) -> dict:
	if not usuario.get("is_admin"):
		raise HTTPException(
			status_code=status.HTTP_403_FORBIDDEN,
			detail="Acesso restrito a administradores"
		)
	return usuario
