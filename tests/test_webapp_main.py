import datetime

from fastapi.testclient import TestClient

from webapp import main


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
    assert "Tecnologia: sem e-mail de gestor configurado" in resposta.text


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

    assert "sem e-mail de gestor configurado" not in resposta.text


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

    destinatarios_chamados = []

    def fake_enviar(token, remetente, destinatarios, periodo, link):
        destinatarios_chamados.extend(destinatarios)
        assert link == "https://painel-fucape.netlify.app/2026-06/"
        return {destinatario: "ok" for destinatario in destinatarios}

    monkeypatch.setattr(main.mailer_graph, "enviar_notificacao", fake_enviar)

    resposta = client.post("/enviar")

    assert resposta.status_code == 200
    assert "ceo@fucape.br" in destinatarios_chamados
    assert "gestor.ti@fucape.br" in destinatarios_chamados
    assert "Todos os envios OK" in resposta.text


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

    def enviar_com_uma_falha(token, remetente, destinatarios, periodo, link):
        return {
            destinatario: ("ok" if destinatario != "gestor.ti@fucape.br" else "erro: 400 endereço inválido")
            for destinatario in destinatarios
        }

    monkeypatch.setattr(main.mailer_graph, "enviar_notificacao", enviar_com_uma_falha)
    client.post("/enviar")
    assert main.ESTADO["ultima_publicacao"]["resultados"]["gestor.ti@fucape.br"].startswith("erro:")

    def reenviar_com_sucesso(token, remetente, destinatarios, periodo, link):
        assert destinatarios == ["gestor.ti@fucape.br"]
        return {"gestor.ti@fucape.br": "ok"}

    monkeypatch.setattr(main.mailer_graph, "enviar_notificacao", reenviar_com_sucesso)

    resposta = client.post("/reenviar")

    assert resposta.status_code == 200
    assert "Todos os envios OK" in resposta.text
    assert main.ESTADO["ultima_publicacao"]["resultados"]["gestor.ti@fucape.br"] == "ok"
