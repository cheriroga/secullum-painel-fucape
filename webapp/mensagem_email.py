from pathlib import Path

CAMINHO_ASSINATURA = Path(__file__).resolve().parent / "assets" / "assinatura_kris.png"
CID_ASSINATURA = "assinatura_kris"


def montar_assunto(periodo: str) -> str:
    return f"Banco de horas da equipe {periodo}"


def montar_corpo_html(periodo: str, link: str) -> str:
    return (
        "<p>Prezados (as)</p>"
        f"<p>Compartilho abaixo o link com o banco de horas da equipe referente ao período de "
        f"{periodo}:</p>"
        f'<p>🔗 <a href="{link}">{link}</a></p>'
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
