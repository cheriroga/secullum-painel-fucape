from webapp.mensagem_email import CAMINHO_ASSINATURA, CID_ASSINATURA, montar_assunto, montar_corpo_html


def test_montar_assunto_inclui_periodo():
    assert montar_assunto("Junho/2026") == "Banco de horas da equipe Junho/2026"


def test_montar_corpo_html_inclui_periodo_e_link():
    corpo = montar_corpo_html("Junho/2026", "https://painel-fucape.netlify.app/2026-06/")

    assert "Junho/2026" in corpo
    assert 'href="https://painel-fucape.netlify.app/2026-06/"' in corpo
    assert "<ul>" in corpo and "</ul>" in corpo


def test_montar_corpo_html_usa_botao_compativel_com_outlook():
    corpo = montar_corpo_html("Junho/2026", "https://painel-fucape.netlify.app/2026-06/")

    # ramo Outlook (VML) e ramo fallback, ambos apontando pro link
    assert "v:roundrect" in corpo
    assert "<!--[if mso]>" in corpo and "<!--[if !mso]><!-- -->" in corpo
    assert corpo.count('href="https://painel-fucape.netlify.app/2026-06/"') == 2
    assert "Abrir o painel de horas" in corpo
    # não deixa mais o link cru repetido como texto visível
    assert "🔗" not in corpo


def test_montar_corpo_html_termina_com_atenciosamente_e_assinatura():
    corpo = montar_corpo_html("Junho/2026", "https://painel-fucape.netlify.app/2026-06/")

    assert "Atenciosamente" in corpo
    assert f'src="cid:{CID_ASSINATURA}"' in corpo


def test_caminho_assinatura_aponta_pro_arquivo_real():
    assert CAMINHO_ASSINATURA.name == "assinatura_kris.png"
    assert CAMINHO_ASSINATURA.exists()
