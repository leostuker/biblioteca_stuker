const ROTULOS_STATUS = {
	quero_ler: "Quero ler",
	lendo: "Lendo",
	lido: "Lido",
	abandonado: "Abandonado",
};

let usuarioAtual = null;
let fluxoCameraAtivo = null;
let leitorAlternativoAtivo = null;

async function chamarApi(caminho, metodo = "GET", corpo = null) {
	const opcoes = { method: metodo, credentials: "same-origin", headers: {} };
	if (corpo !== null) {
		opcoes.headers["Content-Type"] = "application/json";
		opcoes.body = JSON.stringify(corpo);
	}
	const resposta = await fetch(caminho, opcoes);
	const dados = await resposta.json();
	if (!resposta.ok) {
		throw new Error(typeof dados.detail === "string" ? dados.detail : "Dados inválidos. Confira os campos.");
	}
	return dados;
}

function criar(tag, atributos = {}, ...filhos) {
	const elemento = document.createElement(tag);
	for (const [chave, valor] of Object.entries(atributos)) {
		if (chave === "classe") elemento.className = valor;
		else if (chave.startsWith("on")) elemento.addEventListener(chave.slice(2), valor);
		else elemento.setAttribute(chave, valor);
	}
	for (const filho of filhos.flat()) {
		if (filho === null || filho === undefined || filho === false) continue;
		elemento.append(filho);
	}
	return elemento;
}

function mostrarMensagem(texto, ehErro = false) {
	const caixa = document.getElementById("mensagem");
	caixa.textContent = texto;
	caixa.classList.toggle("erro", ehErro);
	caixa.hidden = false;
	caixa.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

function formatarData(valor) {
	if (!valor) return "—";
	return new Date(`${valor.slice(0, 10)}T00:00:00`).toLocaleDateString("pt-BR");
}

function dataEmDias(dias) {
	return new Date(Date.now() + dias * 86400000).toLocaleDateString("sv-SE");
}

function criarElementoEstrelas(nota) {
	const valor = Math.max(0, Math.min(5, Math.round(Number(nota) || 0)));
	return criar("span", {
		classe: "estrelas",
		role: "img",
		"aria-label": `Avaliação: ${valor} de 5 estrelas`,
	}, `${"★".repeat(valor)}${"☆".repeat(5 - valor)} ${Number(nota).toFixed(1)}`);
}

function valorOuNulo(valor) {
	const limpo = valor.trim();
	return limpo === "" ? null : limpo;
}

function numeroOuNulo(valor) {
	const limpo = valor.trim();
	return limpo === "" ? null : Number(limpo);
}

function criarCapa(livro) {
	if (livro.url_capa) {
		return criar("img", { classe: "capa", src: livro.url_capa, alt: `Capa de ${livro.titulo}`, loading: "lazy", referrerpolicy: "no-referrer" });
	}
	return criar("div", { classe: "capa-vazia", "aria-hidden": "true" }, livro.titulo.charAt(0).toUpperCase());
}

function montarNavegacao() {
	const lista = criar("ul");
	lista.append(criar("li", {}, criar("a", { href: "/" }, "Catálogo")));
	if (usuarioAtual) {
		lista.append(criar("li", {}, criar("a", { href: "/emprestimos" }, "Empréstimos")));
		if (usuarioAtual.is_admin) {
			lista.append(criar("li", {}, criar("a", { href: "/adicionar" }, "Adicionar livro")));
		}
		lista.append(criar("li", { classe: "usuario-logado" }, usuarioAtual.nome));
		lista.append(criar("li", {}, criar("button", { type: "button", onclick: sair }, "Sair")));
	} else {
		lista.append(criar("li", {}, criar("a", { href: "/login" }, "Entrar")));
	}
	document.getElementById("navegacao").replaceChildren(lista);
}

async function sair() {
	await chamarApi("/api/auth/logout", "POST");
	window.location.href = "/";
}

function exigirLogin() {
	if (!usuarioAtual) {
		window.location.href = "/login";
		return false;
	}
	return true;
}

function exigirAdmin() {
	if (!exigirLogin()) return false;
	if (!usuarioAtual.is_admin) {
		window.location.href = "/";
		return false;
	}
	return true;
}

function criarSeletorNota(notaInicial) {
	let notaAtual = notaInicial || 0;
	const recipiente = criar("div", { classe: "seletor-nota", role: "group", "aria-label": "Nota de 1 a 5" });
	const botoes = [1, 2, 3, 4, 5].map((valor) =>
		criar("button", {
			type: "button",
			"aria-label": `${valor} ${valor === 1 ? "estrela" : "estrelas"}`,
			onclick: () => {
				notaAtual = notaAtual === valor ? 0 : valor;
				atualizar();
			},
		}, "★")
	);
	const atualizar = () => botoes.forEach((botao, indice) => botao.classList.toggle("ativa", indice < notaAtual));
	atualizar();
	recipiente.append(...botoes);
	recipiente.obterNota = () => notaAtual || null;
	return recipiente;
}

function criarCartaoLivro(livro) {
	const etiquetas = criar("div", { classe: "etiquetas" },
		criar("span", { classe: `etiqueta ${livro.disponivel ? "disponivel" : "emprestado"}` }, livro.disponivel ? "Disponível" : "Emprestado"),
		livro.meu_status && criar("span", { classe: "etiqueta leitura" }, ROTULOS_STATUS[livro.meu_status])
	);
	return criar("a", { classe: "cartao-livro", href: `/livro/${livro.id_livro}` },
		criarCapa(livro),
		criar("div", { classe: "corpo" },
			criar("h3", {}, livro.titulo),
			criar("span", { classe: "autor" }, livro.autor),
			livro.nota_media && criarElementoEstrelas(livro.nota_media),
			etiquetas
		)
	);
}

async function paginaCatalogo() {
	const resumo = await chamarApi("/api/resumo");
	document.getElementById("total-livros").textContent = resumo.total_livros;
	document.getElementById("total-lidos").textContent = resumo.leituras_concluidas;
	document.getElementById("total-emprestados").textContent = resumo.emprestados;
	const seletorGenero = document.getElementById("filtro-genero");
	for (const genero of resumo.generos) {
		seletorGenero.append(criar("option", { value: genero }, genero));
	}
	const formulario = document.getElementById("filtros");
	if (!usuarioAtual) {
		document.getElementById("filtro-status").closest("label").hidden = true;
	}
	const grade = document.getElementById("grade-livros");
	const carregar = async () => {
		const parametros = new URLSearchParams();
		for (const [chave, valor] of new FormData(formulario)) {
			if (valor !== "") parametros.append(chave, valor);
		}
		const livros = await chamarApi(`/api/livros?${parametros}`);
		if (livros.length === 0) {
			grade.replaceChildren(criar("p", { classe: "vazio" }, "Nenhum livro encontrado."));
			return;
		}
		grade.replaceChildren(...livros.map(criarCartaoLivro));
	};
	formulario.addEventListener("submit", (evento) => {
		evento.preventDefault();
		carregar().catch((erro) => mostrarMensagem(erro.message, true));
	});
	formulario.addEventListener("change", () => formulario.requestSubmit());
	await carregar();
}

function blocoCabecalhoLivro(livro) {
	const itens = [
		["Gênero", livro.genero],
		["Ano", livro.ano_publicacao],
		["Páginas", livro.numero_paginas],
		["ISBN", livro.isbn],
	].filter(([, valor]) => valor);
	return criar("section", { classe: "livro-cabecalho" },
		criarCapa(livro),
		criar("div", { classe: "metadados" },
			criar("h1", {}, livro.titulo),
			criar("p", { classe: "autor" }, livro.autor),
			livro.nota_media && criarElementoEstrelas(livro.nota_media),
			criar("div", { classe: "etiquetas" },
				criar("span", { classe: `etiqueta ${livro.disponivel ? "disponivel" : "emprestado"}` }, livro.disponivel ? "Disponível" : "Emprestado")
			),
			criar("dl", {}, itens.flatMap(([rotulo, valor]) => [criar("dt", {}, rotulo), criar("dd", {}, String(valor))])),
			livro.sinopse && criar("p", { classe: "texto-editorial" }, livro.sinopse)
		)
	);
}

function blocoDiario(livro) {
	if (!usuarioAtual) {
		return criar("section", { classe: "bloco" },
			criar("h2", {}, "Meu diário de leitura"),
			criar("p", { classe: "vazio" }, criar("a", { href: "/login" }, "Entre"), " para registrar sua leitura e avaliação.")
		);
	}
	const atual = livro.minha_avaliacao || {};
	const seletorStatus = criar("select", { id: "diario-status", name: "status" },
		Object.entries(ROTULOS_STATUS).map(([valor, rotulo]) => criar("option", { value: valor }, rotulo))
	);
	seletorStatus.value = atual.status || "quero_ler";
	const seletorNota = criarSeletorNota(atual.nota);
	const dataInicio = criar("input", { type: "date", id: "diario-inicio", value: atual.data_inicio || "" });
	const dataConclusao = criar("input", { type: "date", id: "diario-conclusao", value: atual.data_conclusao || "" });
	const resenha = criar("textarea", { id: "diario-resenha", maxlength: "5000" });
	resenha.value = atual.resenha || "";
	const formulario = criar("form", { classe: "formulario" },
		criar("div", { classe: "linha-campos" },
			criar("label", { classe: "campo", for: "diario-status" }, "Status", seletorStatus),
			criar("div", { classe: "campo" }, "Nota", seletorNota)
		),
		criar("div", { classe: "linha-campos" },
			criar("label", { classe: "campo", for: "diario-inicio" }, "Início", dataInicio),
			criar("label", { classe: "campo", for: "diario-conclusao" }, "Término", dataConclusao)
		),
		criar("label", { classe: "campo", for: "diario-resenha" }, "Resenha", resenha),
		criar("button", { classe: "botao", type: "submit" }, "Salvar no diário")
	);
	formulario.addEventListener("submit", async (evento) => {
		evento.preventDefault();
		await chamarApi(`/api/livros/${livro.id_livro}/avaliacao`, "POST", {
			status: seletorStatus.value,
			nota: seletorNota.obterNota(),
			resenha: valorOuNulo(resenha.value),
			data_inicio: dataInicio.value || null,
			data_conclusao: dataConclusao.value || null,
		}).then(() => window.location.reload(), (erro) => mostrarMensagem(erro.message, true));
	});
	return criar("section", { classe: "bloco" }, criar("h2", {}, "Meu diário de leitura"), formulario);
}

function blocoResenhas(livro) {
	const conteudo = livro.avaliacoes.length === 0
		? [criar("p", { classe: "vazio" }, "Ainda não há avaliações para este livro.")]
		: livro.avaliacoes.map((avaliacao) =>
			criar("div", { classe: "resenha" },
				criar("div", { classe: "cabecalho-resenha" },
					criar("strong", {}, avaliacao.nome),
					avaliacao.nota ? criarElementoEstrelas(avaliacao.nota) : criar("span", { classe: "etiqueta leitura" }, ROTULOS_STATUS[avaliacao.status])
				),
				avaliacao.resenha && criar("p", { classe: "texto-editorial" }, avaliacao.resenha)
			)
		);
	return criar("section", { classe: "bloco" }, criar("h2", {}, "Resenhas"), ...conteudo);
}

async function blocoEmprestimoAdmin(livro) {
	const ativo = livro.emprestimo_ativo;
	let acao;
	if (ativo) {
		const botaoDevolver = criar("button", { classe: "botao", type: "button" }, "Marcar como devolvido");
		botaoDevolver.addEventListener("click", () =>
			chamarApi(`/api/emprestimos/${ativo.id_emprestimo}/devolver`, "PUT")
				.then(() => window.location.reload(), (erro) => mostrarMensagem(erro.message, true))
		);
		acao = criar("div", {},
			criar("p", {}, `Emprestado para ${ativo.nome_usuario}, desde ${formatarData(ativo.data_emprestimo)}. Devolução prevista: ${formatarData(ativo.data_prevista)}.`),
			ativo.atrasado && criar("p", { classe: "etiqueta atrasado" }, "Atrasado"),
			botaoDevolver
		);
	} else {
		const usuarios = await chamarApi("/api/usuarios");
		const seletorUsuario = criar("select", { id: "emprestimo-usuario", required: "" },
			usuarios.map((usuario) => criar("option", { value: usuario.id_usuario }, `${usuario.nome} (${usuario.email})`))
		);
		const prazo = criar("input", { type: "date", id: "emprestimo-prazo", value: dataEmDias(14), min: dataEmDias(0), required: "" });
		const observacao = criar("input", { type: "text", id: "emprestimo-observacao", maxlength: "200" });
		acao = criar("form", { classe: "formulario" },
			criar("div", { classe: "linha-campos" },
				criar("label", { classe: "campo", for: "emprestimo-usuario" }, "Emprestar para", seletorUsuario),
				criar("label", { classe: "campo", for: "emprestimo-prazo" }, "Devolução prevista", prazo)
			),
			criar("label", { classe: "campo", for: "emprestimo-observacao" }, "Observação", observacao),
			criar("p", {}, criar("a", { href: "/emprestimos" }, "Precisa cadastrar uma pessoa? Use a tela de empréstimos.")),
			criar("button", { classe: "botao", type: "submit" }, "Registrar empréstimo")
		);
		acao.addEventListener("submit", (evento) => {
			evento.preventDefault();
			chamarApi("/api/emprestimos", "POST", {
				id_livro: livro.id_livro,
				id_usuario: Number(seletorUsuario.value),
				data_prevista: prazo.value,
				observacao: valorOuNulo(observacao.value),
			}).then(() => window.location.reload(), (erro) => mostrarMensagem(erro.message, true));
		});
	}
	const historico = livro.historico_emprestimos.length === 0 ? null : criar("div", { classe: "tabela-rolavel" },
		criar("table", {},
			criar("thead", {}, criar("tr", {}, ["Pessoa", "Saída", "Previsto", "Devolvido"].map((titulo) => criar("th", {}, titulo)))),
			criar("tbody", {}, livro.historico_emprestimos.map((item) =>
				criar("tr", { classe: item.atrasado ? "linha-atrasada" : "" },
					criar("td", {}, item.nome_usuario),
					criar("td", {}, formatarData(item.data_emprestimo)),
					criar("td", {}, formatarData(item.data_prevista)),
					criar("td", {}, formatarData(item.data_devolucao))
				)
			))
		)
	);
	return criar("section", { classe: "bloco" }, criar("h2", {}, "Empréstimo"), acao, historico && criar("h3", {}, "Histórico"), historico);
}

async function paginaLivro() {
	const idLivro = window.location.pathname.split("/").pop();
	const livro = await chamarApi(`/api/livros/${idLivro}`);
	document.title = `${livro.titulo} — Biblioteca Stüker`;
	const raiz = document.getElementById("detalhes");
	const blocos = [blocoCabecalhoLivro(livro), blocoDiario(livro), blocoResenhas(livro)];
	if (usuarioAtual && usuarioAtual.is_admin) {
		blocos.push(await blocoEmprestimoAdmin(livro));
		blocos.push(criarBlocoExcluir(livro));
	}
	raiz.replaceChildren(...blocos);
}

function criarBlocoExcluir(livro) {
	const botao = criar("button", { classe: "botao secundario", type: "button" }, "Excluir livro do acervo");
	botao.addEventListener("click", () => {
		if (!window.confirm(`Excluir "${livro.titulo}" e todo o histórico dele?`)) return;
		chamarApi(`/api/livros/${livro.id_livro}`, "DELETE")
			.then(() => { window.location.href = "/"; }, (erro) => mostrarMensagem(erro.message, true));
	});
	return criar("section", { classe: "bloco" }, botao);
}

async function paginaEmprestimos() {
	if (!exigirLogin()) return;
	const ehAdmin = usuarioAtual.is_admin;
	if (ehAdmin) {
		document.getElementById("bloco-novo-usuario").hidden = false;
		const formulario = document.getElementById("form-novo-usuario");
		formulario.addEventListener("submit", (evento) => {
			evento.preventDefault();
			const dados = new FormData(formulario);
			chamarApi("/api/usuarios", "POST", {
				nome: dados.get("nome"),
				email: dados.get("email"),
				telefone: valorOuNulo(dados.get("telefone")),
				senha: dados.get("senha"),
			}).then(() => {
				formulario.reset();
				mostrarMensagem("Pessoa cadastrada. Agora é só emprestar um livro para ela na página do livro.");
			}, (erro) => mostrarMensagem(erro.message, true));
		});
	}
	const emprestimos = await chamarApi("/api/emprestimos");
	const corpo = document.getElementById("corpo-emprestimos");
	if (emprestimos.length === 0) {
		corpo.replaceChildren(criar("tr", {}, criar("td", { colspan: "6", classe: "vazio" }, "Nenhum empréstimo registrado.")));
		return;
	}
	corpo.replaceChildren(...emprestimos.map((item) => {
		const situacao = item.status === "devolvido" ? "Devolvido" : item.atrasado ? "Atrasado" : "No prazo";
		const celulaAcao = criar("td");
		if (ehAdmin && item.status === "ativo") {
			celulaAcao.append(criar("button", {
				classe: "botao secundario",
				type: "button",
				onclick: () => chamarApi(`/api/emprestimos/${item.id_emprestimo}/devolver`, "PUT")
					.then(() => window.location.reload(), (erro) => mostrarMensagem(erro.message, true)),
			}, "Devolvido"));
		}
		return criar("tr", { classe: item.atrasado ? "linha-atrasada" : "" },
			criar("td", {}, criar("a", { href: `/livro/${item.id_livro}` }, item.titulo)),
			criar("td", {}, item.nome_usuario),
			criar("td", {}, formatarData(item.data_emprestimo)),
			criar("td", {}, formatarData(item.data_prevista)),
			criar("td", {}, situacao),
			celulaAcao
		);
	}));
}

function carregarScript(url) {
	return new Promise((resolver, rejeitar) => {
		const script = document.createElement("script");
		script.src = url;
		script.onload = resolver;
		script.onerror = rejeitar;
		document.head.append(script);
	});
}

async function encerrarScanner() {
	if (fluxoCameraAtivo) {
		fluxoCameraAtivo.getTracks().forEach((faixa) => faixa.stop());
		fluxoCameraAtivo = null;
	}
	if (leitorAlternativoAtivo) {
		try {
			await leitorAlternativoAtivo.stop();
			leitorAlternativoAtivo.clear();
		} catch {
			leitorAlternativoAtivo = null;
		}
		leitorAlternativoAtivo = null;
	}
	const video = document.getElementById("video-scanner");
	if (video) {
		video.pause();
		video.srcObject = null;
		video.hidden = true;
	}
	const alternativo = document.getElementById("leitor-alternativo");
	if (alternativo) {
		alternativo.hidden = true;
	}
	const area = document.getElementById("area-scanner");
	if (area) {
		area.hidden = true;
	}
}

window.addEventListener("pagehide", encerrarScanner);
document.addEventListener("keydown", (evento) => {
	if (evento.key === "Escape" && fluxoCameraAtivo) {
		encerrarScanner();
	}
});

async function iniciarScanner(aoLerCodigo) {
	const area = document.getElementById("area-scanner");
	const video = document.getElementById("video-scanner");
	const alternativo = document.getElementById("leitor-alternativo");
	area.hidden = false;
	const finalizar = (codigo) => {
		encerrarScanner();
		aoLerCodigo(codigo);
	};
	if ("BarcodeDetector" in window) {
		const fluxo = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
		fluxoCameraAtivo = fluxo;
		const detector = new BarcodeDetector({ formats: ["ean_13", "ean_8"] });
		video.hidden = false;
		video.srcObject = fluxo;
		await video.play();
		const ciclo = async () => {
			if (!fluxoCameraAtivo) return;
			const codigos = await detector.detect(video);
			if (codigos.length > 0) return finalizar(codigos[0].rawValue);
			requestAnimationFrame(ciclo);
		};
		ciclo();
		return;
	}
	await carregarScript("https://unpkg.com/html5-qrcode@2.3.8/html5-qrcode.min.js");
	const leitor = new Html5Qrcode("leitor-alternativo");
	leitorAlternativoAtivo = leitor;
	alternativo.hidden = false;
	await leitor.start({ facingMode: "environment" }, { fps: 10 }, (texto) => finalizar(texto));
}

async function paginaAdicionar() {
	if (!exigirAdmin()) return;
	const formulario = document.getElementById("form-livro");
	const campos = formulario.elements;

	const preencher = (dados) => {
		for (const [nome, valor] of Object.entries(dados)) {
			if (campos[nome] && valor !== null && valor !== undefined) campos[nome].value = valor;
		}
	};

	const buscarIsbn = async () => {
		const codigo = document.getElementById("isbn-busca").value.trim();
		if (!codigo) return;
		const dados = await chamarApi(`/api/isbn/${encodeURIComponent(codigo)}`)
			.catch((erro) => { mostrarMensagem(erro.message, true); return null; });
		if (!dados) return;
		preencher(dados);
		mostrarMensagem("Dados encontrados. Confira e salve.");
	};

	document.getElementById("botao-buscar").addEventListener("click", buscarIsbn);
	document.getElementById("isbn-busca").addEventListener("keydown", (evento) => {
		if (evento.key === "Enter") {
			evento.preventDefault();
			buscarIsbn();
		}
	});
	document.getElementById("botao-scanner").addEventListener("click", () =>
		iniciarScanner((codigo) => {
			document.getElementById("isbn-busca").value = codigo;
			buscarIsbn();
		}).catch(() => {
			encerrarScanner();
			mostrarMensagem("Não foi possível usar a câmera. Verifique a permissão ou digite o ISBN.", true);
		})
	);
	document.getElementById("botao-fechar-scanner").addEventListener("click", () => encerrarScanner());

	formulario.addEventListener("submit", (evento) => {
		evento.preventDefault();
		chamarApi("/api/livros", "POST", {
			titulo: campos.titulo.value,
			autor: campos.autor.value,
			genero: valorOuNulo(campos.genero.value),
			ano_publicacao: numeroOuNulo(campos.ano_publicacao.value),
			numero_paginas: numeroOuNulo(campos.numero_paginas.value),
			isbn: valorOuNulo(campos.isbn.value),
			url_capa: valorOuNulo(campos.url_capa.value),
			sinopse: valorOuNulo(campos.sinopse.value),
		}).then(
			(livro) => { window.location.href = `/livro/${livro.id_livro}`; },
			(erro) => mostrarMensagem(erro.message, true)
		);
	});
}

function paginaLogin() {
	if (usuarioAtual) {
		window.location.href = "/";
		return;
	}
	const ligar = (idFormulario, caminho, montarCorpo) => {
		const formulario = document.getElementById(idFormulario);
		formulario.addEventListener("submit", (evento) => {
			evento.preventDefault();
			chamarApi(caminho, "POST", montarCorpo(new FormData(formulario)))
				.then(() => { window.location.href = "/"; }, (erro) => mostrarMensagem(erro.message, true));
		});
	};
	ligar("form-entrar", "/api/auth/login", (dados) => ({ email: dados.get("email"), senha: dados.get("senha") }));
	ligar("form-cadastro", "/api/auth/cadastro", (dados) => ({
		nome: dados.get("nome"),
		email: dados.get("email"),
		telefone: valorOuNulo(dados.get("telefone")),
		senha: dados.get("senha"),
	}));
}

const PAGINAS = {
	catalogo: paginaCatalogo,
	livro: paginaLivro,
	emprestimos: paginaEmprestimos,
	adicionar: paginaAdicionar,
	login: paginaLogin,
};

async function iniciar() {
	try {
		usuarioAtual = (await chamarApi("/api/auth/me")).usuario;
		montarNavegacao();
		await PAGINAS[document.body.dataset.pagina]();
	} catch (erro) {
		mostrarMensagem(erro.message, true);
	}
}

iniciar();
