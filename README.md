# Biblioteca Stüker

Sistema de catalogação e acervo pessoal de livros e leituras.

## Tecnologias

- **Backend:** FastAPI (Python 3.11)
- **Banco de Dados:** PostgreSQL 16
- **Frontend:** HTML5 semântico e CSS3 puro (estilo Tumblr 2012)
- **Containerização:** Docker e Docker Compose

## Estrutura do Projeto

```text
biblioteca_stuker/
├── .env.example
├── .gitignore
├── compose.yaml
├── Dockerfile
├── README.md
├── backend/
│   ├── main.py
│   └── requirements.txt
└── frontend/
    ├── index.html
    └── static/
        ├── favicon.svg
        └── style.css
```

## Execução com Docker

1. Copie o arquivo de variáveis de ambiente:
   ```bash
   cp .env.example .env
   ```

2. Suba os containers:
   ```bash
   docker compose up -d --build
   ```

3. Acesse a aplicação no navegador em `http://localhost:8001`.
