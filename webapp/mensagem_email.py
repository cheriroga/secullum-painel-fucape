from pathlib import Path

CAMINHO_ASSINATURA = Path(__file__).resolve().parent / "assets" / "assinatura_kris.png"
CID_ASSINATURA = "assinatura_kris"


_COR_BOTAO = "#C8102E"  # vermelho Fucape


def montar_assunto(periodo: str) -> str:
    return f"Banco de horas da equipe {periodo}"


def _botao(link: str, texto: str) -> str:
    """Botão 'bulletproof' que renderiza no Outlook (VML via comentário mso) e
    nos demais clientes (tabela + <a> no fallback). O href aparece nos dois
    ramos, então o link continua clicável em qualquer cliente."""
    return (
        '<table role="presentation" cellpadding="0" cellspacing="0" border="0" '
        'width="100%" style="margin:8px 0 20px;"><tr><td align="center">'
        f'<!--[if mso]>'
        f'<v:roundrect xmlns:v="urn:schemas-microsoft-com:vml" '
        f'xmlns:w="urn:schemas-microsoft-com:office:word" href="{link}" '
        f'style="height:48px;v-text-anchor:middle;width:240px;" arcsize="14%" '
        f'strokecolor="{_COR_BOTAO}" fillcolor="{_COR_BOTAO}">'
        f'<w:anchorlock/>'
        f'<center style="color:#FFFFFF;font-family:Arial,Helvetica,sans-serif;'
        f'font-size:15px;font-weight:bold;">{texto}</center>'
        f'</v:roundrect>'
        f'<![endif]-->'
        f'<!--[if !mso]><!-- -->'
        f'<table role="presentation" cellpadding="0" cellspacing="0" border="0">'
        f'<tr><td style="background-color:{_COR_BOTAO};border-radius:6px;">'
        f'<a href="{link}" target="_blank" '
        f'style="display:inline-block;padding:14px 36px;'
        f'font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:bold;'
        f'color:#FFFFFF;text-decoration:none;">{texto}</a>'
        f'</td></tr></table>'
        f'<!--<![endif]-->'
        '</td></tr></table>'
    )


def montar_corpo_html(periodo: str, link: str) -> str:
    return (
        "<p>Prezados (as)</p>"
        f"<p>Compartilho abaixo o banco de horas da equipe referente ao período de "
        f"{periodo}:</p>"
        f"{_botao(link, 'Abrir o painel de horas')}"
        "<p>No relatório é possível acompanhar:</p>"
        "<ul>"
        "<li>O saldo de horas individual de cada colaborador;</li>"
        "<li>O consolidado da equipe no período;</li>"
        "<li>Eventuais saldos positivos ou negativos que mereçam atenção.</li>"
        "</ul>"
        "<p>Caso identifiquem algum ponto que precise de ajuste ou queiram um detalhamento "
        "adicional, é só me avisar.</p>"
        "<p>Atenciosamente,</p>"
        f'<p><img src="cid:{CID_ASSINATURA}" alt="Assinatura" style="max-width:300px"></p>'
    )
