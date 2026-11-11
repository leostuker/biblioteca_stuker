from typing import Optional
from fastapi import APIRouter, Request, Depends, Form, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from backend.seguranca import exigir_admin
from backend.servicos.livros_servico import (
	criar_livro,
	obter_livro_por_id,
	atualizar_livro,
	excluir_livro,
	listar_livros
)
from backend.servicos.emprestimos_servico import (
	listar_emprestimos,
	registrar_emprestimo,
	registrar_devolucao
)
from backend.servicos.usuarios_servico import (
	listar_usuarios,
	alternar_perfil_admin,
	excluir_usuario
)

router = APIRouter(prefix="/admin")
templates = Jinja2Templates(directory="frontend/templates")

@router.get("/livros/novo")
def form_novo_livro(request: Request, admin=Depends(exigir_admin)):
	return templates.TemplateResponse(
		request=request,
		name="admin_livro_form.html",
		context={"usuario": admin, "livro": None}
	)

@router.post("/livros/novo")
def salvar_novo_livro(
	titulo: str = Form(...),
	autor: str = Form(...),
	isbn_13: Optional[str] = Form(None),
	isbn_10: Optional[str] = Form(None),
	editora: Optional[str] = Form(None),
	ano_publicacao: Optional[str] = Form(None),
	paginas: Optional[str] = Form(None),
	sinopse: Optional[str] = Form(None),
	capa_url: Optional[str] = Form(None),
	formato: str = Form("Físico"),
	tags: Optional[str] = Form(None),
	admin=Depends(exigir_admin)
):
	tags_lista = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
	ano = int(ano_publicacao) if ano_publicacao and ano_publicacao.strip().isdigit() else None
	pags = int(paginas) if paginas and paginas.strip().isdigit() else None

	novo = criar_livro(
		titulo=titulo,
		autor=autor,
		isbn_13=isbn_13,
		isbn_10=isbn_10,
		editora=editora,
		ano_publicacao=ano,
		paginas=pags,
		sinopse=sinopse,
		capa_url=capa_url,
		formato=formato,
		tags_lista=tags_lista
	)
	return RedirectResponse(url=f"/livros/{novo['id']}", status_code=303)

@router.get("/livros/{id}/editar")
def form_editar_livro(id: int, request: Request, admin=Depends(exigir_admin)):
	livro = obter_livro_por_id(id)
	if not livro:
		raise HTTPException(status_code=404, detail="Livro não encontrado")
	tags_str = ", ".join(livro.get("tags", []))
	return templates.TemplateResponse(
		request=request,
		name="admin_livro_form.html",
		context={"usuario": admin, "livro": livro, "tags_str": tags_str}
	)

@router.post("/livros/{id}/editar")
def salvar_edicao_livro(
	id: int,
	titulo: str = Form(...),
	autor: str = Form(...),
	isbn_13: Optional[str] = Form(None),
	isbn_10: Optional[str] = Form(None),
	editora: Optional[str] = Form(None),
	ano_publicacao: Optional[str] = Form(None),
	paginas: Optional[str] = Form(None),
	sinopse: Optional[str] = Form(None),
	capa_url: Optional[str] = Form(None),
	formato: str = Form("Físico"),
	tags: Optional[str] = Form(None),
	admin=Depends(exigir_admin)
):
	tags_lista = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
	ano = int(ano_publicacao) if ano_publicacao and ano_publicacao.strip().isdigit() else None
	pags = int(paginas) if paginas and paginas.strip().isdigit() else None

	atualizar_livro(
		livro_id=id,
		titulo=titulo,
		autor=autor,
		isbn_13=isbn_13,
		isbn_10=isbn_10,
		editora=editora,
		ano_publicacao=ano,
		paginas=pags,
		sinopse=sinopse,
		capa_url=capa_url,
		formato=formato,
		tags_lista=tags_lista
	)
	return RedirectResponse(url=f"/livros/{id}", status_code=303)

@router.post("/livros/{id}/excluir")
def deletar_livro(id: int, admin=Depends(exigir_admin)):
	excluir_livro(id)
	return RedirectResponse(url="/", status_code=303)

@router.get("/emprestimos")
def pagina_emprestimos(request: Request, admin=Depends(exigir_admin)):
	emprestimos = listar_emprestimos()
	livros_disponiveis = [l for l in listar_livros() if l.get("disponivel")]
	return templates.TemplateResponse(
		request=request,
		name="admin_emprestimos.html",
		context={
			"usuario": admin,
			"emprestimos": emprestimos,
			"livros": livros_disponiveis
		}
	)

@router.post("/emprestimos/novo")
def criar_emprestimo(
	livro_id: int = Form(...),
	nome_destinatario: str = Form(...),
	contato: Optional[str] = Form(None),
	data_previsao: Optional[str] = Form(None),
	observacoes: Optional[str] = Form(None),
	admin=Depends(exigir_admin)
):
	registrar_emprestimo(
		livro_id=livro_id,
		nome_destinatario=nome_destinatario,
		contato=contato,
		data_previsao=data_previsao if data_previsao else None,
		observacoes=observacoes
	)
	return RedirectResponse(url="/admin/emprestimos", status_code=303)

@router.post("/emprestimos/{id}/devolver")
def devolver_livro(id: int, admin=Depends(exigir_admin)):
	registrar_devolucao(id)
	return RedirectResponse(url="/admin/emprestimos", status_code=303)

@router.get("/usuarios")
def gerenciar_usuarios(request: Request, admin=Depends(exigir_admin)):
	usuarios = listar_usuarios()
	return templates.TemplateResponse(
		request=request,
		name="admin_usuarios.html",
		context={"usuario": admin, "usuarios": usuarios}
	)

@router.post("/usuarios/{id}/perfil")
def alternar_status_usuario(id: int, admin=Depends(exigir_admin)):
	if id != admin["id"]:
		alternar_perfil_admin(id)
	return RedirectResponse(url="/admin/usuarios", status_code=303)

@router.post("/usuarios/{id}/excluir")
def remover_usuario(id: int, admin=Depends(exigir_admin)):
	if id != admin["id"]:
		excluir_usuario(id)
	return RedirectResponse(url="/admin/usuarios", status_code=303)
