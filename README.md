# Biblioteca Stüker

Sistema de biblioteca pessoal: acervo, diário de leitura com avaliações individuais, controle de empréstimos e cadastro de livros por ISBN ou código de barras.

Stack: FastAPI, PostgreSQL (psycopg2, sem ORM), HTML + CSS puro.

## Perfis

- **Visitante:** navega pelo catálogo e lê as resenhas.
- **Leitor:** tem conta, registra status de leitura, nota (1 a 5) e resenha próprios, e vê seus empréstimos.
- **Admin:** cadastra, edita e exclui livros, cadastra pessoas e registra empréstimos e devoluções. O primeiro admin é criado a partir do `.env`.

## Deploy com Docker

```bash
git clone https://github.com/leostuker/biblioteca_stuker.git
cd biblioteca_stuker
cp .env.example .env
docker compose up -d --build
```

Antes de subir, edite o `.env`:

- `DB_PASS` e `ADMIN_PASS`: senhas fortes.
- `SECRET_KEY`: gere com `python -c "import secrets; print(secrets.token_hex(32))"`.
- `ADMIN_EMAIL`: e-mail do administrador.
- `COOKIE_SEGURO=true` é o correto atrás do Cloudflare (HTTPS). Para testar por `http://` no IP da rede local, use `false`.
- `BIND_IP=127.0.0.1` expõe a porta só no próprio servidor, que é o que o `cloudflared` precisa. Use `0.0.0.0` para acessar pela rede local.

A aplicação sobe na porta **5789**. O banco só é acessível pela rede interna do Compose.

O `init.sql` roda apenas na primeira criação do volume `pgdata`. Para recriar o banco do zero: `docker compose down -v`.

## Cloudflare Tunnel

Com o `cloudflared` rodando no servidor, aponte o hostname público para `http://localhost:5789`.

O HTTPS do túnel é necessário para o scanner de código de barras, porque o navegador só libera a câmera em conexão segura.

O login não tem limite de tentativas na aplicação. Use as regras de rate limit da Cloudflare em `/api/auth/login`.

## Scanner de código de barras

Em `/adicionar`, o botão "Escanear código de barras" abre a câmera. Usa o `BarcodeDetector` nativo (Chrome Android) e, quando indisponível, carrega a biblioteca `html5-qrcode` como alternativa.

## API para app mobile

A API aceita o cookie de sessão ou o cabeçalho `Authorization: Bearer <token>`. O token vem em `POST /api/auth/login`. A documentação interativa está em `/docs`.

## Testes

Os testes de integração exigem um banco **exclusivo de teste**, pois o schema é recriado a cada execução.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt

set DB_USER=postgres
set DB_PASS=sua_senha
set TEST_DB_NAME=biblioteca_teste
pytest -v
```

Sem `TEST_DB_NAME`, os testes que dependem de banco são ignorados e apenas os de segurança rodam.
