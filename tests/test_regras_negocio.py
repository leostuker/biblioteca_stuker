from datetime import date, timedelta


def prazo(dias=14):
	return (date.today() + timedelta(days=dias)).isoformat()


def test_cada_leitor_tem_sua_propria_avaliacao(cliente, criar_livro, criar_leitor):
	id_livro = criar_livro()
	ana = criar_leitor("ana@teste.com", "Ana")
	bia = criar_leitor("bia@teste.com", "Bia")
	cliente.post(f"/api/livros/{id_livro}/avaliacao", json={"status": "lido", "nota": 5, "resenha": "Amei"}, headers=ana["cabecalho"])
	cliente.post(f"/api/livros/{id_livro}/avaliacao", json={"status": "abandonado", "nota": 1}, headers=bia["cabecalho"])
	detalhe_ana = cliente.get(f"/api/livros/{id_livro}", headers=ana["cabecalho"]).json()
	detalhe_bia = cliente.get(f"/api/livros/{id_livro}", headers=bia["cabecalho"]).json()
	assert detalhe_ana["minha_avaliacao"]["nota"] == 5
	assert detalhe_bia["minha_avaliacao"]["status"] == "abandonado"
	assert float(detalhe_ana["nota_media"]) == 3.0
	assert len(detalhe_ana["avaliacoes"]) == 2


def test_reavaliar_atualiza_sem_duplicar(cliente, criar_livro, criar_leitor):
	id_livro = criar_livro()
	ana = criar_leitor("ana@teste.com")
	cliente.post(f"/api/livros/{id_livro}/avaliacao", json={"status": "lendo"}, headers=ana["cabecalho"])
	cliente.post(f"/api/livros/{id_livro}/avaliacao", json={"status": "lido", "nota": 4}, headers=ana["cabecalho"])
	detalhe = cliente.get(f"/api/livros/{id_livro}", headers=ana["cabecalho"]).json()
	assert detalhe["minha_avaliacao"]["status"] == "lido"
	assert len(detalhe["avaliacoes"]) == 1


def test_nota_fora_do_intervalo_retorna_422(cliente, criar_livro, criar_leitor):
	id_livro = criar_livro()
	ana = criar_leitor("ana@teste.com")
	resposta = cliente.post(f"/api/livros/{id_livro}/avaliacao", json={"status": "lido", "nota": 6}, headers=ana["cabecalho"])
	assert resposta.status_code == 422


def test_isbn_duplicado_retorna_409(cliente, cabecalho_admin, criar_livro):
	criar_livro(isbn="978-85-359-0277-8")
	resposta = cliente.post("/api/livros", json={"titulo": "Outro", "autor": "Alguem", "isbn": "9788535902778"}, headers=cabecalho_admin)
	assert resposta.status_code == 409


def test_nao_empresta_livro_ja_emprestado(cliente, cabecalho_admin, criar_livro, criar_leitor):
	id_livro = criar_livro()
	ana = criar_leitor("ana@teste.com")
	bia = criar_leitor("bia@teste.com")
	primeiro = cliente.post("/api/emprestimos", json={"id_livro": id_livro, "id_usuario": ana["id_usuario"], "data_prevista": prazo()}, headers=cabecalho_admin)
	segundo = cliente.post("/api/emprestimos", json={"id_livro": id_livro, "id_usuario": bia["id_usuario"], "data_prevista": prazo()}, headers=cabecalho_admin)
	assert primeiro.status_code == 201
	assert segundo.status_code == 409


def test_devolucao_libera_livro_para_novo_emprestimo(cliente, cabecalho_admin, criar_livro, criar_leitor):
	id_livro = criar_livro()
	ana = criar_leitor("ana@teste.com")
	corpo = {"id_livro": id_livro, "id_usuario": ana["id_usuario"], "data_prevista": prazo()}
	id_emprestimo = cliente.post("/api/emprestimos", json=corpo, headers=cabecalho_admin).json()["id_emprestimo"]
	assert cliente.get(f"/api/livros/{id_livro}").json()["disponivel"] is False
	assert cliente.put(f"/api/emprestimos/{id_emprestimo}/devolver", headers=cabecalho_admin).status_code == 200
	assert cliente.get(f"/api/livros/{id_livro}").json()["disponivel"] is True
	assert cliente.post("/api/emprestimos", json=corpo, headers=cabecalho_admin).status_code == 201


def test_emprestimo_com_data_no_passado_retorna_422(cliente, cabecalho_admin, criar_livro, criar_leitor):
	id_livro = criar_livro()
	ana = criar_leitor("ana@teste.com")
	corpo = {"id_livro": id_livro, "id_usuario": ana["id_usuario"], "data_prevista": prazo(-1)}
	assert cliente.post("/api/emprestimos", json=corpo, headers=cabecalho_admin).status_code == 422


def test_emprestimo_de_livro_inexistente_retorna_404(cliente, cabecalho_admin, criar_leitor):
	ana = criar_leitor("ana@teste.com")
	corpo = {"id_livro": 999, "id_usuario": ana["id_usuario"], "data_prevista": prazo()}
	assert cliente.post("/api/emprestimos", json=corpo, headers=cabecalho_admin).status_code == 404


def test_leitor_ve_apenas_seus_emprestimos(cliente, cabecalho_admin, criar_livro, criar_leitor):
	primeiro_livro = criar_livro("Livro A")
	segundo_livro = criar_livro("Livro B")
	ana = criar_leitor("ana@teste.com")
	bia = criar_leitor("bia@teste.com")
	cliente.post("/api/emprestimos", json={"id_livro": primeiro_livro, "id_usuario": ana["id_usuario"], "data_prevista": prazo()}, headers=cabecalho_admin)
	cliente.post("/api/emprestimos", json={"id_livro": segundo_livro, "id_usuario": bia["id_usuario"], "data_prevista": prazo()}, headers=cabecalho_admin)
	lista_ana = cliente.get("/api/emprestimos", headers=ana["cabecalho"]).json()
	lista_admin = cliente.get("/api/emprestimos", headers=cabecalho_admin).json()
	assert [item["titulo"] for item in lista_ana] == ["Livro A"]
	assert len(lista_admin) == 2


def test_leitor_nao_registra_emprestimo(cliente, criar_livro, criar_leitor):
	id_livro = criar_livro()
	ana = criar_leitor("ana@teste.com")
	corpo = {"id_livro": id_livro, "id_usuario": ana["id_usuario"], "data_prevista": prazo()}
	assert cliente.post("/api/emprestimos", json=corpo, headers=ana["cabecalho"]).status_code == 403


def test_busca_trata_curingas_como_texto(cliente, criar_livro):
	criar_livro("100% Verdade", "Autor Um")
	criar_livro("Outro Livro", "Autor Dois")
	assert len(cliente.get("/api/livros", params={"busca": "%"}).json()) == 1
	assert len(cliente.get("/api/livros", params={"busca": "autor"}).json()) == 2


def test_filtro_de_disponibilidade(cliente, cabecalho_admin, criar_livro, criar_leitor):
	livre = criar_livro("Livre")
	emprestado = criar_livro("Emprestado")
	ana = criar_leitor("ana@teste.com")
	cliente.post("/api/emprestimos", json={"id_livro": emprestado, "id_usuario": ana["id_usuario"], "data_prevista": prazo()}, headers=cabecalho_admin)
	disponiveis = cliente.get("/api/livros", params={"disponivel": True}).json()
	assert [livro["id_livro"] for livro in disponiveis] == [livre]


def test_filtro_por_meu_status(cliente, criar_livro, criar_leitor):
	lido = criar_livro("Lido")
	criar_livro("Nao lido")
	ana = criar_leitor("ana@teste.com")
	cliente.post(f"/api/livros/{lido}/avaliacao", json={"status": "lido"}, headers=ana["cabecalho"])
	resposta = cliente.get("/api/livros", params={"status_leitura": "lido"}, headers=ana["cabecalho"]).json()
	assert [livro["id_livro"] for livro in resposta] == [lido]


def test_historico_de_emprestimos_so_aparece_para_admin(cliente, cabecalho_admin, criar_livro, criar_leitor):
	id_livro = criar_livro()
	ana = criar_leitor("ana@teste.com")
	cliente.post("/api/emprestimos", json={"id_livro": id_livro, "id_usuario": ana["id_usuario"], "data_prevista": prazo()}, headers=cabecalho_admin)
	como_admin = cliente.get(f"/api/livros/{id_livro}", headers=cabecalho_admin).json()
	como_leitor = cliente.get(f"/api/livros/{id_livro}", headers=ana["cabecalho"]).json()
	assert como_admin["emprestimo_ativo"]["nome_usuario"] == "Leitor"
	assert como_leitor["emprestimo_ativo"] is None
	assert como_leitor["historico_emprestimos"] == []


def test_health(cliente):
	assert cliente.get("/health").json() == {"status": "ok"}


def test_cabecalhos_de_seguranca_presentes(cliente):
	resposta = cliente.get("/health")
	assert resposta.headers["X-Frame-Options"] == "DENY"
	assert "Content-Security-Policy" in resposta.headers
