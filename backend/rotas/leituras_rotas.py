from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from backend.seguranca import obter_usuario_logado
from backend.servicos.leituras_servico import (
	obter_leituras_usuario,
	atualizar_status_leitura,
	salvar_resenha
)

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")

@router.get("/minhas-leituras")
def pagina_minhas_leituras(request: Request, usuario=Depends(obter_usuario_logado)):
	leituras = obter_leituras_usuario(usuario["id"])
	return templates.TemplateResponse(
		request=request,
		name="minhas_leituras.html",
		context={
			"usuario": usuario,
			"leituras": leituras
		}
	)

@router.post("/livros/{id}/status-leitura")
def atualizar_status(
	id: int,
	status: str = Form(...),
	origem: str = Form(""),
	usuario=Depends(obter_usuario_logado)
):
	atualizar_status_leitura(usuario["id"], id, status)
	url_redirecionamento = origem if origem else f"/livros/{id}"
	return RedirectResponse(url=url_redirecionamento, status_code=303)

@router.post("/livros/{id}/resenha")
def postar_resenha(
	id: int,
	nota: int = Form(...),
	texto: str = Form(""),
	usuario=Depends(obter_usuario_logado)
):
	salvar_resenha(usuario["id"], id, nota, texto)
	return RedirectResponse(url=f"/livros/{id}", status_code=303)
