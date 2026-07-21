from webapp.config import carregar_config, salvar_config, tem_algum_email


def test_carregar_config_arquivo_inexistente_retorna_vazio(tmp_path):
    assert carregar_config(tmp_path / "config.json") == {"ceo_email": "", "gestores": {}}


def test_salvar_e_carregar_config_roundtrip(tmp_path):
    caminho = tmp_path / "sub" / "config.json"
    config = {
        "ceo_email": "ceo@fucape.br",
        "gestores": {"TECNOLOGIA": "gestor.ti@fucape.br", "MARKETING": "gestor.mkt@fucape.br"},
    }

    salvar_config(caminho, config)

    assert carregar_config(caminho) == config


def test_tem_algum_email_falso_quando_config_vazia():
    assert tem_algum_email({"ceo_email": "", "gestores": {}}) is False


def test_tem_algum_email_verdadeiro_so_com_ceo():
    assert tem_algum_email({"ceo_email": "ceo@fucape.br", "gestores": {}}) is True


def test_tem_algum_email_verdadeiro_so_com_gestor():
    assert tem_algum_email({"ceo_email": "", "gestores": {"TECNOLOGIA": "gestor.ti@fucape.br"}}) is True
