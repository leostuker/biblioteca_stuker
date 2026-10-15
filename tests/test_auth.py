SENHA_PADRAO = "senha-leitor-123"


def test_admin_inicial_consegue_logar(cliente):
	resposta = cliente.post("/api/auth/login", json={"email": "admin@teste.com", "senha": "senha-admin-123"})
	assert resposta.status_code == 200
	assert resposta.json()["usuario"]["is_admin"] is True


def test_login_com_senha_errada_retorna_401(cliente):
	resposta = cliente.post("/api/auth/login", json={"email": "admin@teste.com", "senha": "errada-errada"})
	assert resposta.status_code == 401


def test_cadastro_cria_leitor_comum_e_loga(cliente):
	resposta = cliente.post(
		"/api/auth/cadastro",
		json={"nome": "Maria", "email": "Maria@Teste.com", "senha": SENHA_PADRAO},
	)
	assert resposta.status_code == 201
	assert resposta.json()["usuario"]["is_admin"] is False
	assert resposta.json()["usuario"]["email"] == "maria@teste.com"
	assert cliente.get("/api/auth/me").json()["usuario"]["nome"] == "Maria"


def test_cadastro_com_email_repetido_retorna_409(cliente):
	corpo = {"nome": "Maria", "email": "maria@teste.com", "senha": SENHA_PADRAO}
	cliente.post("/api/auth/cadastro", json=corpo)
	assert cliente.post("/api/auth/cadastro", json=corpo).status_code == 409


def test_cadastro_com_senha_curta_retorna_422(cliente):
	resposta = cliente.post("/api/auth/cadastro", json={"nome": "Maria", "email": "m@t.com", "senha": "123"})
	assert resposta.status_code == 422


def test_bearer_token_autentica(cliente, cabecalho_admin):
	resposta = cliente.get("/api/auth/me", headers=cabecalho_admin)
	assert resposta.json()["usuario"]["email"] == "admin@teste.com"


def test_visitante_nao_cadastra_livro(cliente):
	resposta = cliente.post("/api/livros", json={"titulo": "X", "autor": "Y"})
	assert resposta.status_code == 401


def test_leitor_nao_cadastra_livro(cliente, criar_leitor):
	leitor = criar_leitor("leitor@teste.com")
	resposta = cliente.post("/api/livros", json={"titulo": "X", "autor": "Y"}, headers=leitor["cabecalho"])
	assert resposta.status_code == 403


def test_leitor_nao_lista_usuarios(cliente, criar_leitor):
	leitor = criar_leitor("leitor@teste.com")
	assert cliente.get("/api/usuarios", headers=leitor["cabecalho"]).status_code == 403


def test_admin_cria_cadastro_para_leitor(cliente, cabecalho_admin):
	resposta = cliente.post(
		"/api/usuarios",
		json={"nome": "Amigo", "email": "amigo@teste.com", "senha": SENHA_PADRAO},
		headers=cabecalho_admin,
	)
	assert resposta.status_code == 201
	assert resposta.json()["is_admin"] is False
