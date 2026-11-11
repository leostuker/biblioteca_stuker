from typing import Optional
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.templating import Jinja2Templates
from backend.seguranca import obter_usuario_opcional
from backend.servicos.livros_servico import listar_livros, obter_livro_por_id, listar_tags_populares
from backend.servicos.leituras_servico import obter_status_leitura_livro, obter_resenha_usuario

router = APIRouter()
templates = Jinja2Templates(directory="frontend/templates")

@router.get("/")
def pagina_catalogo(
	request: Request,
	q: Optional[str] = None,
	tag: Optional[str] = None,
	usuario_logado=Depends(obter_usuario_opcional)
):
	livros = listar_livros(termo_busca=q, tag=tag)
	tags_populares = listar_tags_populares(limite=25)
	return templates.TemplateResponse(
		request=request,
		name="catalogo.html",
		context={
			"usuario": usuario_logado,
			"livros": livros,
			"tags_populares": tags_populares,
			"termo_busca": q or "",
			"tag_filtro": tag or ""
		}
	)

@router.get("/livros/{id}")
def detalhes_livro(
	id: int,
	request: Request,
	usuario_logado=Depends(obter_usuario_opcional)
):
	livro = obter_livro_por_id(id)
	if not livro:
		raise HTTPException(status_code=404, detail="Livro não encontrado")

	meu_status = None
	minha_resenha = None
	if usuario_logado:
		meu_status = obter_status_leitura_livro(usuario_logado["id"], id)
		minha_resenha = obter_resenha_usuario(usuario_logado["id"], id)

	return templates.TemplateResponse(
		request=request,
		name="livro_detalhes.html",
		context={
			"usuario": usuario_logado,
			"livro": livro,
			"meu_status": meu_status,
			"minha_resenha": minha_resenha
		}
	)
