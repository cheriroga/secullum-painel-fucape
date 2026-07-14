from webapp.config import carregar_config, salvar_config


def test_carregar_config_arquivo_inexistente_retorna_vazio(tmp_path):
    assert carregar_config(tmp_path / "config.json") == {}


def test_salvar_e_carregar_config_roundtrip(tmp_path):
    caminho = tmp_path / "sub" / "config.json"
    mapa = {"TECNOLOGIA": "gestor.ti@fucape.br", "MARKETING": "gestor.mkt@fucape.br"}

    salvar_config(caminho, mapa)

    assert carregar_config(caminho) == mapa
