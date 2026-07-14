from webapp.mensagem_email import montar_assunto, montar_corpo_html


def test_montar_assunto_inclui_periodo():
    assert montar_assunto("Junho/2026") == "Banco de horas da equipe Junho/2026"


def test_montar_corpo_html_inclui_periodo_e_link():
    corpo = montar_corpo_html("Junho/2026", "https://painel-fucape.netlify.app/2026-06/")

    assert "Junho/2026" in corpo
    assert 'href="https://painel-fucape.netlify.app/2026-06/"' in corpo
    assert "<ul>" in corpo and "</ul>" in corpo
    assert "kristielledantas@fucape.br" in corpo
