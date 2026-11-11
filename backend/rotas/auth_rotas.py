from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from backend.seguranca import criar_token_sessao, obter_usuario_opcional
from backend.servicos.usuarios_servico import autenticar_usuario, criar_usuario

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")

@router.get("/login")
def pagina_login(request: Request, usuario_logado=Depends(obter_usuario_opcional)):
	if usuario_logado:
		return RedirectResponse(url="/", status_code=303)
	return templates.TemplateResponse(
		request=request,
		name="login.html",
		context={"usuario": None, "erro": None}
	)

@router.post("/login")
def processar_login(request: Request, usuario: str = Form(...), senha: str = Form(...)):
	usuario_autenticado = autenticar_usuario(usuario, senha)
	if not usuario_autenticado:
		return templates.TemplateResponse(
			request=request,
			name="login.html",
			context={"usuario": None, "erro": "Usuário ou senha incorretos."},
			status_code=400
		)
	resposta = RedirectResponse(url="/", status_code=303)
	token = criar_token_sessao(usuario_autenticado["id"])
	resposta.set_cookie(
		key="sessao_stuker",
		value=token,
		httponly=True,
		max_age=86400 * 14,
		samesite="lax"
	)
	return resposta

@router.get("/registro")
def pagina_registro(request: Request, usuario_logado=Depends(obter_usuario_opcional)):
	if usuario_logado:
		return RedirectResponse(url="/", status_code=303)
	return templates.TemplateResponse(
		request=request,
		name="registro.html",
		context={"usuario": None, "erro": None}
	)

@router.post("/registro")
def processar_registro(
	request: Request,
	nome: str = Form(...),
	usuario: str = Form(...),
	email: str = Form(""),
	senha: str = Form(...)
):
	try:
		novo_usuario = criar_usuario(nome, usuario, email, senha, is_admin=False)
	except Exception:
		return templates.TemplateResponse(
			request=request,
			name="registro.html",
			context={"usuario": None, "erro": "Usuário ou e-mail já cadastrado."},
			status_code=400
		)
	resposta = RedirectResponse(url="/", status_code=303)
	token = criar_token_sessao(novo_usuario["id"])
	resposta.set_cookie(
		key="sessao_stuker",
		value=token,
		httponly=True,
		max_age=86400 * 14,
		samesite="lax"
	)
	return resposta

@router.get("/logout")
@router.post("/logout")
def processar_logout():
	resposta = RedirectResponse(url="/", status_code=303)
	resposta.delete_cookie("sessao_stuker")
	return resposta
