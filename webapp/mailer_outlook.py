import os

import pythoncom
import win32com.client

from webapp.mensagem_email import CAMINHO_ASSINATURA, CID_ASSINATURA, montar_assunto, montar_corpo_html

# Propriedade MAPI PidTagAttachContentId - liga o anexo ao <img src="cid:...">
PROPRIEDADE_MAPI_CID = "http://schemas.microsoft.com/mapi/proptag/0x3712001F"

# Conta de envio quando há várias no Outlook. Sem isso, o Outlook usa a conta
# padrão do perfil (que nesta máquina é outra pessoa). Configurável por env.
REMETENTE_PADRAO = os.environ.get("PAINEL_REMETENTE_OUTLOOK", "kristielledantas@fucape.br")

# dispid de MailItem.SendUsingAccount — é property put-by-ref, não dá pra
# atribuir direto no pywin32, precisa do Invoke de baixo nível.
_DISPID_SEND_USING_ACCOUNT = 64209


class EnvioError(RuntimeError):
    pass


def _achar_conta(session, smtp: str):
    contas = session.Accounts
    for i in range(1, contas.Count + 1):
        conta = contas.Item(i)
        try:
            if (conta.SmtpAddress or "").lower() == smtp.lower():
                return conta
        except Exception:
            continue
    return None


def _usar_conta(email, conta) -> None:
    email._oleobj_.Invoke(
        _DISPID_SEND_USING_ACCOUNT, 0, pythoncom.DISPATCH_PROPERTYPUTREF, 0, conta,
    )


def enviar_notificacao(
    destinatarios_links: dict[str, str], periodo: str, remetente: str | None = None,
) -> dict[str, str]:
    """Manda um e-mail por destinatário via Outlook Desktop já logado na
    máquina (COM automation) — sem precisar de credenciais Graph. Envia pela
    conta `remetente` (default REMETENTE_PADRAO), não pela conta padrão do
    perfil."""
    remetente = remetente or REMETENTE_PADRAO
    try:
        outlook = win32com.client.Dispatch("Outlook.Application")
    except Exception as exc:
        raise EnvioError(
            f"Não foi possível conectar ao Outlook — verifique se está instalado e logado: {exc}"
        ) from exc

    conta = _achar_conta(outlook.Session, remetente)
    if conta is None:
        raise EnvioError(
            f"A conta {remetente} não está configurada no Outlook desta máquina — "
            "não dá pra enviar por ela."
        )

    assunto = montar_assunto(periodo)
    resultados: dict[str, str] = {}

    for destinatario, link in destinatarios_links.items():
        try:
            email = outlook.CreateItem(0)  # olMailItem
            _usar_conta(email, conta)
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
