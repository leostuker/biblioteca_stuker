# Biblioteca Stüker

Sistema completo de catalogação e acervo pessoal de livros e leituras, desenvolvido em FastAPI com PostgreSQL puro (sem ORM) e interface server-side rendering (Jinja2) inspirada na estética do Tumblr de 2012.

## Tecnologias

- **Backend:** FastAPI (Python 3.11)
- **Banco de Dados:** PostgreSQL 16 (acesso via `psycopg2` com pool de conexões)
- **Frontend:** Jinja2 SSR, HTML5 semântico e CSS3 puro (estética Tumblr 2012, sem frameworks JS)
- **Containerização:** Docker e Docker Compose

## Funcionalidades

- **Catálogo em Ordem Alfabética:** listagem alfabética de todos os títulos com capa, autor, ano e status.
- **Busca e Filtro por Tags:** busca por texto livre (título, autor, ISBN) e navegação por hashtags temáticas.
- **Ficha Detalhada da Obra:** metadados ricos (editora, páginas, formato, ISBN-10, ISBN-13, sinopse).
- **Estante Pessoal (Minhas Leituras):** acompanhamento individual por status (*Lendo*, *Quero Ler*, *Lido*, *Abandonado*).
- **Avaliações e Resenhas:** notas de 1 a 5 estrelas e resenhas textuais dos leitores.
- **Controle de Empréstimos Informais:** registro de empréstimos com destinatário, contato e previsão de devolução.
- **Painel Administrativo:** catalogação de novos títulos, edição, exclusão, controle de acervo e gerenciamento de usuários.
- **Carga de Dados Automática:** importação no primeiro boot a partir do acervo `dados/libib.csv`.

## Credenciais Padrão

- **Administrador:** `leo`
- **Senha:** `1998`

## Execução com Docker

1. Clone o repositório e configure as variáveis de ambiente:
   ```bash
   cp .env.example .env
   ```

2. Inicie os containers:
   ```bash
   docker compose up -d --build
   ```

3. Acesse a aplicação no navegador em:
   ```
   http://localhost:8001
   ```

## Testes Automatizados

Para executar os testes com pytest via container:
```bash
docker run --rm -e PYTHONPATH=/app -v $(pwd)/tests:/app/tests biblioteca_stuker-api pytest -v tests/
```
