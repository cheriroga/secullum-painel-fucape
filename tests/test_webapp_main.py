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
