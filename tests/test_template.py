from painel_horas.calculos import montar_relatorio, montar_pessoa
from painel_horas.parser import Colaborador, Dia
from painel_horas.template import render_pagina, render_pessoa
import datetime


def _colab_simples(nome, departamento, valor_min):
    dia = Dia(
        data=datetime.date(2026, 1, 15), dia_semana="Qui",
        ent1=datetime.timedelta(hours=8), sai1=datetime.timedelta(hours=17),
        ent2=None, sai2=None, ent3=None, sai3=None,
        ex50_min=0, atraso_min=0, btotal_min=valor_min, exnot_min=0,
    )
    return Colaborador(
        nome=nome, funcao="Cargo", admissao=datetime.date(2020, 1, 1), departamento=departamento,
        dias=[dia], total_bruto_min=valor_min,
    )


def test_render_pagina_geral_contem_secoes_esperadas():
    r = montar_relatorio([_colab_simples("Fulano", "TECNOLOGIA", 100)], escopo="geral")
    html = render_pagina({
        "escopo_titulo": "Painel do CEO", "periodo_texto": "01/01/2026 → 09/07/2026",
        "data_emissao": "10/07/2026", "mostrar_deptos": True, "r": r,
    })
    assert "<!DOCTYPE html>" in html
    assert "Painel do CEO" in html
    assert "Fulano" in html
    assert "Saldo por departamento" in html
    assert 'href="../tecnologia/index.html"' in html
    assert "<script>" in html and "<link" not in html


def test_render_pagina_depto_omite_secao_deptos():
    r = montar_relatorio([_colab_simples("Ciclano", "BIBLIOTECA", -50)], escopo="depto")
    html = render_pagina({
        "escopo_titulo": "Painel Biblioteca", "periodo_texto": "01/01/2026 → 09/07/2026",
        "data_emissao": "10/07/2026", "mostrar_deptos": False, "r": r,
    })
    assert "Saldo por departamento" not in html
    assert "Ciclano" in html


def test_render_pagina_escapes_html_special_chars():
    # Regression test for XSS vulnerability: verify HTML characters are escaped
    r = montar_relatorio([_colab_simples("Fulano <script>alert(1)</script> & Cia", "TECNOLOGIA", 100)], escopo="geral")
    html = render_pagina({
        "escopo_titulo": "Painel do CEO", "periodo_texto": "01/01/2026 → 09/07/2026",
        "data_emissao": "10/07/2026", "mostrar_deptos": True, "r": r,
    })
    # Raw unescaped tag must not appear
    assert "<script>alert(1)</script>" not in html
    # Escaped version must appear in the HTML output
    assert "&lt;script&gt;" in html
    # Ampersand must also be escaped
    assert "&amp;" in html


def test_render_pessoa_contem_secoes_esperadas():
    c = _colab_simples("Fulano", "TECNOLOGIA", 100)
    html = render_pessoa(montar_pessoa(c))
    assert "<!DOCTYPE html>" in html
    assert "Fulano" in html
    assert "Resumo mensal" in html
    assert "Diário completo" in html
    assert "<script>" in html and "<link" not in html


def test_render_pessoa_escapes_html_special_chars():
    c = _colab_simples("Fulano <script>alert(1)</script> & Cia", "TECNOLOGIA", 100)
    html = render_pessoa(montar_pessoa(c))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_render_pessoa_mostra_periodo_quando_fornecido():
    c = _colab_simples("Fulano", "TECNOLOGIA", 100)
    html = render_pessoa(montar_pessoa(c, periodo_texto="01/01/2026 → 09/07/2026"))
    assert "Período" in html
    assert "01/01/2026 → 09/07/2026" in html


def test_render_pessoa_omite_periodo_quando_vazio():
    c = _colab_simples("Fulano", "TECNOLOGIA", 100)
    html = render_pessoa(montar_pessoa(c))
    assert "Período" not in html


def test_render_pagina_linka_nome_para_pagina_de_pessoa():
    r = montar_relatorio([_colab_simples("Fulano", "TECNOLOGIA", 100)], escopo="geral", prefixo_pessoas="deptos/pessoas/")
    html = render_pagina({
        "escopo_titulo": "Painel do CEO", "periodo_texto": "01/01/2026 → 09/07/2026",
        "data_emissao": "10/07/2026", "mostrar_deptos": True, "r": r,
    })
    assert 'href="deptos/pessoas/fulano.html"' in html
