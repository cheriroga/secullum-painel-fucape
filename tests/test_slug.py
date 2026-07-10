from painel_horas.slug import slugify


def test_slugify_nomes_simples():
    assert slugify("Hub Fucape") == "hub-fucape"
    assert slugify("Tecnologia") == "tecnologia"
    assert slugify("Biblioteca") == "biblioteca"
    assert slugify("Diretoria") == "diretoria"
    assert slugify("Administrativo") == "administrativo"
    assert slugify("Atendimento") == "atendimento"
    assert slugify("Marketing") == "marketing"


def test_slugify_remove_acentos():
    assert slugify("Comunicação") == "comunicacao"
    assert slugify("Secretaria Academica") == "secretaria-academica"


def test_slugify_remove_conectivos():
    assert slugify("Centro de Serviços Compartilhados") == "centro-servicos-compartilhados"
    assert slugify("Secretaria de Pesquisa") == "secretaria-pesquisa"
    assert slugify("Coordenação de Curso") == "coordenacao-curso"
    assert slugify("Gente e Cultura") == "gente-cultura"
