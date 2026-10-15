CREATE TYPE status_leitura AS ENUM ('quero_ler', 'lendo', 'lido', 'abandonado');
CREATE TYPE status_emprestimo AS ENUM ('ativo', 'devolvido');

CREATE TABLE usuarios (
	id_usuario SERIAL PRIMARY KEY,
	nome VARCHAR(255) NOT NULL,
	email VARCHAR(255) NOT NULL UNIQUE,
	telefone VARCHAR(50),
	senha_hash VARCHAR(255) NOT NULL,
	is_admin BOOLEAN NOT NULL DEFAULT FALSE,
	data_cadastro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE livros (
	id_livro SERIAL PRIMARY KEY,
	titulo VARCHAR(255) NOT NULL,
	autor VARCHAR(255) NOT NULL,
	genero VARCHAR(100),
	ano_publicacao INTEGER,
	numero_paginas INTEGER,
	isbn VARCHAR(20) UNIQUE,
	url_capa TEXT,
	sinopse TEXT,
	data_cadastro TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE avaliacoes (
	id_avaliacao SERIAL PRIMARY KEY,
	id_livro INTEGER NOT NULL REFERENCES livros(id_livro) ON DELETE CASCADE,
	id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE CASCADE,
	status status_leitura NOT NULL DEFAULT 'quero_ler',
	nota INTEGER CHECK (nota BETWEEN 1 AND 5),
	resenha TEXT,
	data_inicio DATE,
	data_conclusao DATE,
	data_atualizacao TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	CONSTRAINT avaliacoes_livro_usuario_unico UNIQUE (id_livro, id_usuario)
);

CREATE TABLE emprestimos (
	id_emprestimo SERIAL PRIMARY KEY,
	id_livro INTEGER NOT NULL REFERENCES livros(id_livro) ON DELETE CASCADE,
	id_usuario INTEGER NOT NULL REFERENCES usuarios(id_usuario) ON DELETE RESTRICT,
	data_emprestimo DATE NOT NULL DEFAULT CURRENT_DATE,
	data_prevista DATE NOT NULL,
	data_devolucao DATE,
	status status_emprestimo NOT NULL DEFAULT 'ativo',
	observacao TEXT
);

CREATE UNIQUE INDEX emprestimos_um_ativo_por_livro ON emprestimos (id_livro) WHERE status = 'ativo';
CREATE INDEX livros_titulo_idx ON livros (titulo);
CREATE INDEX livros_autor_idx ON livros (autor);
CREATE INDEX emprestimos_usuario_idx ON emprestimos (id_usuario);
