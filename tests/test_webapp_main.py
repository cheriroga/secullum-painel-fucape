import datetime
import threading

from fastapi.testclient import TestClient

from webapp import main


def test_post_heartbeat_atualiza_timestamp():
    client = TestClient(main.app)
    main.ULTIMO_HEARTBEAT["quando"] = 0

    resposta = client.post("/heartbeat")

    assert resposta.status_code == 200
    assert main.ULTIMO_HEARTBEAT["quando"] > 0


def test_iniciar_monitor_heartbeat_inicia_thread_em_segundo_plano():
    contagem_antes = threading.active_count()

    main.iniciar_monitor_heartbeat(timeout_segundos=1000)

    assert threading.active_count() == contagem_antes + 1


def _dia_com_batida(data_str, btotal_str):
    return (data_str, "Qui", datetime.timedelta(hours=8), datetime.timedelta(hours=17),
            None, None, None, None, None, None, btotal_str, None)


def test_get_index_mostra_formulario_de_upload():
    client = TestClient(main.app)

    resposta = client.get("/")

    assert resposta.status_code == 200
    assert 'enctype="multipart/form-data"' in resposta.text


def test_post_upload_processa_arquivo_e_redireciona_pro_preview(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    main.ESTADO.clear()

    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    client = TestClient(main.app)

    with caminho.open("rb") as arquivo:
        resposta = client.post(
            "/upload",
            files={"arquivo": ("cartaoponto.xlsx", arquivo,
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            follow_redirects=False,
        )

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/preview"
    assert main.ESTADO["ultimo"]["periodo"] == "2026-06"
    assert (tmp_path / "painel_web" / "2026-06" / "index.html").exists()


def test_post_upload_arquivo_invalido_mostra_erro_sem_avancar(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    main.ESTADO.clear()

    caminho = workbook_path([])  # nenhum colaborador reconhecível
    client = TestClient(main.app)

    with caminho.open("rb") as arquivo:
        resposta = client.post(
            "/upload",
            files={"arquivo": ("cartaoponto.xlsx", arquivo,
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )

    assert resposta.status_code == 200
    assert "Nenhum colaborador reconhecido" in resposta.text
    assert "ultimo" not in main.ESTADO


def test_get_preview_sem_upload_redireciona_pro_index():
    main.ESTADO.clear()
    client = TestClient(main.app)

    resposta = client.get("/preview", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"


def test_get_preview_apos_upload_mostra_resumo_e_iframe(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(main, "CAMINHO_CONFIG", tmp_path / "config.json")
    main.ESTADO.clear()

    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    client = TestClient(main.app)
    with caminho.open("rb") as arquivo:
        client.post("/upload", files={"arquivo": ("cartaoponto.xlsx", arquivo,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    resposta = client.get("/preview")

    assert resposta.status_code == 200
    assert "2026-06" in resposta.text
    assert '/painel/2026-06/index.html' in resposta.text
    assert 'name="email_Tecnologia"' in resposta.text
    assert 'Tecnologia <span class="badge-warn">sem e-mail</span>' in resposta.text


def test_get_preview_sem_departamento_faltando_nao_mostra_alerta(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(main, "CAMINHO_CONFIG", tmp_path / "config.json")
    main.ESTADO.clear()

    from webapp.config import salvar_config
    salvar_config(tmp_path / "config.json", {"Tecnologia": "gestor.ti@fucape.br"})

    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    client = TestClient(main.app)
    with caminho.open("rb") as arquivo:
        client.post("/upload", files={"arquivo": ("cartaoponto.xlsx", arquivo,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    resposta = client.get("/preview")

    assert '<span class="badge-warn">' not in resposta.text


def test_post_config_salva_mapa_e_redireciona(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "CAMINHO_CONFIG", tmp_path / "config.json")
    client = TestClient(main.app)

    resposta = client.post(
        "/config", data={"email_Tecnologia": "gestor.ti@fucape.br", "email_Vazio": ""},
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/preview"
    from webapp.config import carregar_config
    assert carregar_config(tmp_path / "config.json") == {"Tecnologia": "gestor.ti@fucape.br"}


def test_post_enviar_sem_upload_redireciona_pro_index():
    main.ESTADO.clear()
    client = TestClient(main.app)

    resposta = client.post("/enviar", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"


def test_post_enviar_publica_e_notifica_com_sucesso(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(main, "CAMINHO_CONFIG", tmp_path / "config.json")
    main.ESTADO.clear()

    from webapp.config import salvar_config
    salvar_config(tmp_path / "config.json", {"Tecnologia": "gestor.ti@fucape.br"})

    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    client = TestClient(main.app)
    with caminho.open("rb") as arquivo:
        client.post("/upload", files={"arquivo": ("cartaoponto.xlsx", arquivo,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    monkeypatch.setenv("PAINEL_CEO_EMAIL", "ceo@fucape.br")
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "segredo")

    monkeypatch.setattr(main.deploy_netlify, "publicar", lambda pasta_base: "https://painel-fucape.netlify.app")
    monkeypatch.setattr(main.mailer_graph, "obter_token", lambda *a, **k: "token-123")

    links_chamados = {}

    def fake_enviar(token, remetente, destinatarios_links, periodo):
        links_chamados.update(destinatarios_links)
        return {destinatario: "ok" for destinatario in destinatarios_links}

    monkeypatch.setattr(main.mailer_graph, "enviar_notificacao", fake_enviar)

    resposta = client.post("/enviar", data={"email_Tecnologia": "gestor.ti@fucape.br"})

    assert resposta.status_code == 200
    assert links_chamados["ceo@fucape.br"] == "https://painel-fucape.netlify.app/2026-06/"
    assert links_chamados["gestor.ti@fucape.br"] == "https://painel-fucape.netlify.app/2026-06/deptos/tecnologia.html"
    assert "Todos os envios OK" in resposta.text


def test_post_enviar_ceo_tambem_gestor_recebe_link_geral_nao_o_do_depto(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(main, "CAMINHO_CONFIG", tmp_path / "config.json")
    main.ESTADO.clear()

    from webapp.config import salvar_config
    salvar_config(tmp_path / "config.json", {"Tecnologia": "ceo@fucape.br"})

    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    client = TestClient(main.app)
    with caminho.open("rb") as arquivo:
        client.post("/upload", files={"arquivo": ("cartaoponto.xlsx", arquivo,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    monkeypatch.setenv("PAINEL_CEO_EMAIL", "ceo@fucape.br")
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "segredo")

    monkeypatch.setattr(main.deploy_netlify, "publicar", lambda pasta_base: "https://painel-fucape.netlify.app")
    monkeypatch.setattr(main.mailer_graph, "obter_token", lambda *a, **k: "token-123")

    links_chamados = {}

    def fake_enviar(token, remetente, destinatarios_links, periodo):
        links_chamados.update(destinatarios_links)
        return {destinatario: "ok" for destinatario in destinatarios_links}

    monkeypatch.setattr(main.mailer_graph, "enviar_notificacao", fake_enviar)

    client.post("/enviar", data={"email_Tecnologia": "ceo@fucape.br"})

    assert links_chamados == {"ceo@fucape.br": "https://painel-fucape.netlify.app/2026-06/"}


def test_post_enviar_salva_config_antes_de_publicar_mesmo_sem_clicar_salvar(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(main, "CAMINHO_CONFIG", tmp_path / "config.json")
    main.ESTADO.clear()

    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    client = TestClient(main.app)
    with caminho.open("rb") as arquivo:
        client.post("/upload", files={"arquivo": ("cartaoponto.xlsx", arquivo,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    monkeypatch.setenv("PAINEL_CEO_EMAIL", "ceo@fucape.br")
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "segredo")
    monkeypatch.setattr(main.deploy_netlify, "publicar", lambda pasta_base: "https://painel-fucape.netlify.app")
    monkeypatch.setattr(main.mailer_graph, "obter_token", lambda *a, **k: "token-123")
    monkeypatch.setattr(
        main.mailer_graph, "enviar_notificacao",
        lambda token, remetente, destinatarios_links, periodo: {d: "ok" for d in destinatarios_links},
    )

    # ninguém clicou em "Salvar configuração" antes — só editou o campo e clicou direto em "Enviar"
    resposta = client.post("/enviar", data={"email_Tecnologia": "novo.gestor@fucape.br"})

    assert resposta.status_code == 200
    from webapp.config import carregar_config
    assert carregar_config(tmp_path / "config.json") == {"Tecnologia": "novo.gestor@fucape.br"}
    assert "novo.gestor@fucape.br" in main.ESTADO["ultima_publicacao"]["resultados"]


def test_post_enviar_modo_teste_nao_chama_netlify_nem_graph(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(main, "CAMINHO_CONFIG", tmp_path / "config.json")
    main.ESTADO.clear()

    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    client = TestClient(main.app)
    with caminho.open("rb") as arquivo:
        client.post("/upload", files={"arquivo": ("cartaoponto.xlsx", arquivo,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    monkeypatch.setenv("PAINEL_CEO_EMAIL", "ceo@fucape.br")
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "segredo")
    monkeypatch.setenv("PAINEL_MODO_TESTE", "1")

    def nao_deveria_chamar(*a, **k):
        raise AssertionError("não deveria chamar Netlify/Graph em modo teste")

    monkeypatch.setattr(main.deploy_netlify, "publicar", nao_deveria_chamar)
    monkeypatch.setattr(main.mailer_graph, "obter_token", nao_deveria_chamar)
    monkeypatch.setattr(main.mailer_graph, "enviar_notificacao", nao_deveria_chamar)

    resposta = client.post("/enviar", data={"email_Tecnologia": "gestor.ti@fucape.br"})

    assert resposta.status_code == 200
    assert "Modo teste ativo" in resposta.text
    resultados = main.ESTADO["ultima_publicacao"]["resultados"]
    assert resultados["ceo@fucape.br"] == "ok"
    assert resultados["gestor.ti@fucape.br"] == "ok"


def test_post_reenviar_modo_teste_nao_chama_graph(tmp_path, monkeypatch):
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "segredo")
    monkeypatch.setenv("PAINEL_MODO_TESTE", "1")

    main.ESTADO.clear()
    main.ESTADO["ultima_publicacao"] = {
        "link_geral": "https://modo-teste.invalido/2026-06/",
        "periodo": "2026-06",
        "resultados": {"gestor.ti@fucape.br": "erro: 400 endereço inválido"},
        "links": {"gestor.ti@fucape.br": "https://modo-teste.invalido/2026-06/deptos/tecnologia.html"},
    }

    def nao_deveria_chamar(*a, **k):
        raise AssertionError("não deveria chamar Graph em modo teste")

    monkeypatch.setattr(main.mailer_graph, "obter_token", nao_deveria_chamar)
    monkeypatch.setattr(main.mailer_graph, "enviar_notificacao", nao_deveria_chamar)

    client = TestClient(main.app)
    resposta = client.post("/reenviar")

    assert resposta.status_code == 200
    assert "Modo teste ativo" in resposta.text
    assert main.ESTADO["ultima_publicacao"]["resultados"]["gestor.ti@fucape.br"] == "ok"


def test_post_enviar_com_falha_de_deploy_nao_envia_email(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(main, "CAMINHO_CONFIG", tmp_path / "config.json")
    main.ESTADO.clear()

    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    client = TestClient(main.app)
    with caminho.open("rb") as arquivo:
        client.post("/upload", files={"arquivo": ("cartaoponto.xlsx", arquivo,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    monkeypatch.setenv("PAINEL_CEO_EMAIL", "ceo@fucape.br")
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "segredo")

    def falha_deploy(pasta_base):
        raise main.deploy_netlify.DeployError("not authenticated")

    monkeypatch.setattr(main.deploy_netlify, "publicar", falha_deploy)

    chamado = []
    monkeypatch.setattr(main.mailer_graph, "obter_token", lambda *a, **k: chamado.append(1))

    resposta = client.post("/enviar")

    assert resposta.status_code == 200
    assert "Falha ao publicar" in resposta.text
    assert chamado == []


def test_post_enviar_sem_variavel_de_ambiente_nao_publica_nem_envia(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(main, "CAMINHO_CONFIG", tmp_path / "config.json")
    main.ESTADO.clear()

    monkeypatch.delenv("PAINEL_CEO_EMAIL", raising=False)
    monkeypatch.delenv("GRAPH_TENANT_ID", raising=False)
    monkeypatch.delenv("GRAPH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GRAPH_CLIENT_SECRET", raising=False)

    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    client = TestClient(main.app)
    with caminho.open("rb") as arquivo:
        client.post("/upload", files={"arquivo": ("cartaoponto.xlsx", arquivo,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    def publicar_nao_deveria_ser_chamado(pasta_base):
        raise AssertionError("deploy_netlify.publicar não deveria ser chamado sem as variáveis de ambiente")

    monkeypatch.setattr(main.deploy_netlify, "publicar", publicar_nao_deveria_ser_chamado)

    chamado = []
    monkeypatch.setattr(main.mailer_graph, "obter_token", lambda *a, **k: chamado.append(1))

    resposta = client.post("/enviar")

    assert resposta.status_code == 200
    assert "Falta configurar variável de ambiente" in resposta.text
    assert chamado == []


def test_post_reenviar_sem_publicacao_redireciona_pro_index():
    main.ESTADO.clear()
    client = TestClient(main.app)

    resposta = client.post("/reenviar", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"


def test_post_reenviar_manda_so_pra_quem_falhou(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(main, "CAMINHO_CONFIG", tmp_path / "config.json")
    main.ESTADO.clear()

    from webapp.config import salvar_config
    salvar_config(tmp_path / "config.json", {"Tecnologia": "gestor.ti@fucape.br"})

    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    client = TestClient(main.app)
    with caminho.open("rb") as arquivo:
        client.post("/upload", files={"arquivo": ("cartaoponto.xlsx", arquivo,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    monkeypatch.setenv("PAINEL_CEO_EMAIL", "ceo@fucape.br")
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "segredo")
    monkeypatch.setattr(main.deploy_netlify, "publicar", lambda pasta_base: "https://painel-fucape.netlify.app")
    monkeypatch.setattr(main.mailer_graph, "obter_token", lambda *a, **k: "token-123")

    def enviar_com_uma_falha(token, remetente, destinatarios_links, periodo):
        return {
            destinatario: ("ok" if destinatario != "gestor.ti@fucape.br" else "erro: 400 endereço inválido")
            for destinatario in destinatarios_links
        }

    monkeypatch.setattr(main.mailer_graph, "enviar_notificacao", enviar_com_uma_falha)
    client.post("/enviar", data={"email_Tecnologia": "gestor.ti@fucape.br"})
    assert main.ESTADO["ultima_publicacao"]["resultados"]["gestor.ti@fucape.br"].startswith("erro:")

    def reenviar_com_sucesso(token, remetente, destinatarios_links, periodo):
        assert list(destinatarios_links.keys()) == ["gestor.ti@fucape.br"]
        assert destinatarios_links["gestor.ti@fucape.br"] == \
            "https://painel-fucape.netlify.app/2026-06/deptos/tecnologia.html"
        return {"gestor.ti@fucape.br": "ok"}

    monkeypatch.setattr(main.mailer_graph, "enviar_notificacao", reenviar_com_sucesso)

    resposta = client.post("/reenviar")

    assert resposta.status_code == 200
    assert "Todos os envios OK" in resposta.text
    assert main.ESTADO["ultima_publicacao"]["resultados"]["gestor.ti@fucape.br"] == "ok"


def test_post_enviar_com_falha_de_autenticacao_graph_mostra_link_e_marca_falhas(
    tmp_path, monkeypatch, workbook_path,
):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(main, "CAMINHO_CONFIG", tmp_path / "config.json")
    main.ESTADO.clear()

    from webapp.config import salvar_config
    salvar_config(tmp_path / "config.json", {"Tecnologia": "gestor.ti@fucape.br"})

    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    client = TestClient(main.app)
    with caminho.open("rb") as arquivo:
        client.post("/upload", files={"arquivo": ("cartaoponto.xlsx", arquivo,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    monkeypatch.setenv("PAINEL_CEO_EMAIL", "ceo@fucape.br")
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "segredo")

    monkeypatch.setattr(main.deploy_netlify, "publicar", lambda pasta_base: "https://painel-fucape.netlify.app")

    def falha_auth(*a, **k):
        raise main.mailer_graph.EnvioError("bad creds")

    monkeypatch.setattr(main.mailer_graph, "obter_token", falha_auth)

    resposta = client.post("/enviar", data={"email_Tecnologia": "gestor.ti@fucape.br"})

    assert resposta.status_code == 200
    assert "painel-fucape.netlify.app" in resposta.text
    resultados = main.ESTADO["ultima_publicacao"]["resultados"]
    assert resultados["ceo@fucape.br"] != "ok"
    assert resultados["gestor.ti@fucape.br"] != "ok"
    assert "falha de autenticação Graph" in resposta.text


def test_post_reenviar_com_falha_de_autenticacao_graph_mantem_falha(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(main, "CAMINHO_CONFIG", tmp_path / "config.json")
    main.ESTADO.clear()

    from webapp.config import salvar_config
    salvar_config(tmp_path / "config.json", {"Tecnologia": "gestor.ti@fucape.br"})

    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    client = TestClient(main.app)
    with caminho.open("rb") as arquivo:
        client.post("/upload", files={"arquivo": ("cartaoponto.xlsx", arquivo,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    monkeypatch.setenv("PAINEL_CEO_EMAIL", "ceo@fucape.br")
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "segredo")
    monkeypatch.setattr(main.deploy_netlify, "publicar", lambda pasta_base: "https://painel-fucape.netlify.app")
    monkeypatch.setattr(main.mailer_graph, "obter_token", lambda *a, **k: "token-123")

    def enviar_com_uma_falha(token, remetente, destinatarios_links, periodo):
        return {
            destinatario: ("ok" if destinatario != "gestor.ti@fucape.br" else "erro: 400 endereço inválido")
            for destinatario in destinatarios_links
        }

    monkeypatch.setattr(main.mailer_graph, "enviar_notificacao", enviar_com_uma_falha)
    client.post("/enviar", data={"email_Tecnologia": "gestor.ti@fucape.br"})
    assert main.ESTADO["ultima_publicacao"]["resultados"]["gestor.ti@fucape.br"].startswith("erro:")

    def falha_auth(*a, **k):
        raise main.mailer_graph.EnvioError("bad creds")

    monkeypatch.setattr(main.mailer_graph, "obter_token", falha_auth)

    resposta = client.post("/reenviar")

    assert resposta.status_code == 200
    resultado_gestor = main.ESTADO["ultima_publicacao"]["resultados"]["gestor.ti@fucape.br"]
    assert resultado_gestor != "ok"
