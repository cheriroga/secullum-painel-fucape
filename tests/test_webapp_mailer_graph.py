import pytest

from webapp import mailer_graph


class _RespostaFalsa:
    def __init__(self, status_code, texto=""):
        self.status_code = status_code
        self.text = texto


def test_obter_token_sucesso(monkeypatch):
    class AppFalsa:
        def __init__(self, client_id, authority, client_credential):
            pass

        def acquire_token_for_client(self, scopes):
            return {"access_token": "token-123"}

    monkeypatch.setattr(mailer_graph.msal, "ConfidentialClientApplication", AppFalsa)

    token = mailer_graph.obter_token("tenant", "client", "segredo")

    assert token == "token-123"


def test_obter_token_falha_levanta_envio_error(monkeypatch):
    class AppFalsa:
        def __init__(self, client_id, authority, client_credential):
            pass

        def acquire_token_for_client(self, scopes):
            return {"error_description": "credenciais inválidas"}

    monkeypatch.setattr(mailer_graph.msal, "ConfidentialClientApplication", AppFalsa)

    with pytest.raises(mailer_graph.EnvioError):
        mailer_graph.obter_token("tenant", "client", "segredo")


def test_enviar_notificacao_marca_ok_e_erro_por_destinatario(monkeypatch):
    chamadas = []

    def fake_post(url, headers, json, timeout):
        chamadas.append(json["message"]["toRecipients"][0]["emailAddress"]["address"])
        if "falha@fucape.br" in chamadas[-1]:
            return _RespostaFalsa(400, "endereço inválido")
        return _RespostaFalsa(202)

    monkeypatch.setattr(mailer_graph.requests, "post", fake_post)

    resultado = mailer_graph.enviar_notificacao(
        token="token-123", remetente="relatorios@fucape.br",
        destinatarios=["ceo@fucape.br", "falha@fucape.br"],
        periodo="2026-06", link="https://painel-fucape.netlify.app/2026-06/",
    )

    assert resultado["ceo@fucape.br"] == "ok"
    assert resultado["falha@fucape.br"].startswith("erro:")
    assert len(chamadas) == 2
