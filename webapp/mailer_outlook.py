import win32com.client

from webapp.mensagem_email import CAMINHO_ASSINATURA, CID_ASSINATURA, montar_assunto, montar_corpo_html

# Propriedade MAPI PidTagAttachContentId - liga o anexo ao <img src="cid:...">
PROPRIEDADE_MAPI_CID = "http://schemas.microsoft.com/mapi/proptag/0x3712001F"


class EnvioError(RuntimeError):
    pass


def enviar_notificacao(destinatarios_links: dict[str, str], periodo: str) -> dict[str, str]:
    """Manda um e-mail por destinatário via Outlook Desktop já logado na
    máquina (COM automation) — sem precisar de credenciais Graph."""
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
    except Exception as exc:
        raise EnvioError(
            f"Não foi possível conectar ao Outlook — verifique se está instalado e logado: {exc}"
        ) from exc

    assunto = montar_assunto(periodo)
    resultados: dict[str, str] = {}

    for destinatario, link in destinatarios_links.items():
        try:
            email = outlook.CreateItem(0)  # olMailItem
            email.To = destinatario
            email.Subject = assunto
            email.HTMLBody = montar_corpo_html(periodo, link)
            anexo = email.Attachments.Add(str(CAMINHO_ASSINATURA))
            anexo.PropertyAccessor.SetProperty(PROPRIEDADE_MAPI_CID, CID_ASSINATURA)
            email.Send()
            resultados[destinatario] = "ok"
        except Exception as exc:
            resultados[destinatario] = f"erro: falha ao enviar via Outlook — {exc}"

    return resultados
