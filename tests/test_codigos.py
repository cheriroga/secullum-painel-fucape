import json
import random

from painel_horas.codigos import MapaCodigos, caminho_dicionario


def _rng():
    return random.Random(1234)


def test_codigo_tem_letra_digito_e_comprimento_fixo():
    mapa = MapaCodigos({}, rng=_rng())
    codigo = mapa.codigo("Atendimento")
    assert len(codigo) == 6
    assert codigo.isalnum() and codigo.islower()
    assert any(c.isalpha() for c in codigo)
    assert any(c.isdigit() for c in codigo)


def test_codigo_e_estavel_para_o_mesmo_label():
    mapa = MapaCodigos({}, rng=_rng())
    primeiro = mapa.codigo("Gente e Cultura")
    assert mapa.codigo("Gente e Cultura") == primeiro


def test_labels_diferentes_recebem_codigos_diferentes():
    mapa = MapaCodigos({}, rng=_rng())
    a = mapa.codigo("Atendimento")
    b = mapa.codigo("Tecnologia")
    assert a != b


def test_nao_e_derivavel_do_nome():
    # o código não pode conter o slug do departamento — se contivesse, um gestor
    # adivinharia a URL do vizinho só sabendo o nome dele.
    mapa = MapaCodigos({}, rng=_rng())
    assert "atendimento" not in mapa.codigo("Atendimento")
    assert "gente" not in mapa.codigo("Gente e Cultura")


def test_carregar_reusa_codigos_ja_gravados(tmp_path):
    caminho = tmp_path / "deptos_codigos.json"
    caminho.write_text(json.dumps({"Atendimento": "k7m2a9"}), encoding="utf-8")

    mapa = MapaCodigos.carregar(caminho)
    assert mapa.codigo("Atendimento") == "k7m2a9"


def test_carregar_arquivo_inexistente_comeca_vazio(tmp_path):
    mapa = MapaCodigos.carregar(tmp_path / "nao_existe.json")
    assert mapa.codigo("Tecnologia")  # gera sem estourar


def test_salvar_e_recarregar_preserva_o_mapeamento(tmp_path):
    caminho = tmp_path / "sub" / "deptos_codigos.json"
    mapa = MapaCodigos.carregar(caminho, rng=_rng())
    codigo = mapa.codigo("Biblioteca")
    mapa.salvar()

    recarregado = MapaCodigos.carregar(caminho)
    assert recarregado.codigo("Biblioteca") == codigo


def test_caminho_dicionario_fica_em_webapp_data(tmp_path):
    caminho = caminho_dicionario(tmp_path)
    assert caminho == tmp_path / "webapp_data" / "deptos_codigos.json"
