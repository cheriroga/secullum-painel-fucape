import msal
import requests


class EnvioError(RuntimeError):
    pass


def obter_token(tenant_id: str, client_id: str, client_secret: str) -> str:
    app = msal.ConfidentialClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
        client_credential=client_secret,
    )
    resultado = app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
    token = resultado.get("access_token")
    if not token:
        raise EnvioError(f"Falha ao autenticar no Graph API: {resultado.get('error_description')}")
    return token


def enviar_notificacao(
    token: str, remetente: str, destinatarios: list[str], periodo: str, link: str,
) -> dict[str, str]:
    resultados: dict[str, str] = {}
    assunto = f"Painel de horas — {periodo} disponível"
    conteudo = f"O painel de horas de {periodo} já está disponível: {link}"

    for destinatario in destinatarios:
        payload = {
            "message": {
                "subject": assunto,
                "body": {"contentType": "Text", "content": conteudo},
                "toRecipients": [{"emailAddress": {"address": destinatario}}],
            }
        }
        try:
            resposta = requests.post(
                f"https://graph.microsoft.com/v1.0/users/{remetente}/sendMail",
                headers={"Authorization": f"Bearer {token}"},
                json=payload,
                timeout=30,
            )
        except requests.exceptions.RequestException as exc:
            resultados[destinatario] = f"erro: falha de conexão — {exc}"
            continue

        if resposta.status_code == 202:
            resultados[destinatario] = "ok"
        else:
            resultados[destinatario] = f"erro: {resposta.status_code} {resposta.text[:200]}"

    return resultados
