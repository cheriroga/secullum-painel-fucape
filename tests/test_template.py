from painel_horas.calculos import montar_relatorio
from painel_horas.parser import Colaborador, Mes
from painel_horas.template import render_pagina
import datetime


def _colab_simples(nome, departamento, valor_min):
    return Colaborador(
        nome=nome, funcao="Cargo", admissao=datetime.date(2020, 1, 1), departamento=departamento,
        meses=[Mes(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), valor_min, max(valor_min, 0), max(-valor_min, 0), 0)],
        total_bruto_min=valor_min, credito_total_min=max(valor_min, 0), debito_total_min=max(-valor_min, 0),
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
    assert "deptos/tecnologia.html" in html
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
