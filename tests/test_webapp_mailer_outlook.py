import pytest

from webapp import mailer_outlook


class _FakeMailItem:
    def __init__(self):
        self.To = None
        self.Subject = None
        self.HTMLBody = None
        self.enviado = False

    def Send(self):
        self.enviado = True


class _FakeOutlookApp:
    def __init__(self):
        self.itens_criados = []

    def CreateItem(self, tipo_item):
        item = _FakeMailItem()
        self.itens_criados.append(item)
        return item


def test_enviar_notificacao_manda_um_email_por_destinatario(monkeypatch):
    app_falso = _FakeOutlookApp()
    monkeypatch.setattr(mailer_outlook.win32com.client, "Dispatch", lambda nome: app_falso)

    resultado = mailer_outlook.enviar_notificacao(
        {
            "ceo@fucape.br": "https://painel-fucape.netlify.app/2026-06/",
            "gestor.ti@fucape.br": "https://painel-fucape.netlify.app/2026-06/deptos/tecnologia.html",
        },
        "Junho/2026",
    )

    assert resultado == {"ceo@fucape.br": "ok", "gestor.ti@fucape.br": "ok"}
    assert len(app_falso.itens_criados) == 2
    assert app_falso.itens_criados[0].To == "ceo@fucape.br"
    assert app_falso.itens_criados[0].Subject == "Banco de horas da equipe Junho/2026"
    assert app_falso.itens_criados[0].enviado is True
    assert "deptos/tecnologia.html" in app_falso.itens_criados[1].HTMLBody


def test_enviar_notificacao_outlook_indisponivel_levanta_envio_error(monkeypatch):
    def dispatch_falho(nome):
        raise Exception("Outlook não está instalado")

    monkeypatch.setattr(mailer_outlook.win32com.client, "Dispatch", dispatch_falho)

    with pytest.raises(mailer_outlook.EnvioError):
        mailer_outlook.enviar_notificacao({"ceo@fucape.br": "https://x/2026-06/"}, "Junho/2026")


def test_enviar_notificacao_marca_erro_por_destinatario_sem_abortar_os_outros(monkeypatch):
    class _MailItemFalhaNoSend(_FakeMailItem):
        def Send(self):
            raise Exception("mensagem recusada")

    class _AppComUmaFalha:
        def __init__(self):
            self.chamadas = 0

        def CreateItem(self, tipo_item):
            self.chamadas += 1
            if self.chamadas == 1:
                return _MailItemFalhaNoSend()
            return _FakeMailItem()

    monkeypatch.setattr(mailer_outlook.win32com.client, "Dispatch", lambda nome: _AppComUmaFalha())

    resultado = mailer_outlook.enviar_notificacao(
        {"falha@fucape.br": "https://x/", "ok@fucape.br": "https://x/"}, "Junho/2026",
    )

    assert resultado["falha@fucape.br"].startswith("erro:")
    assert resultado["ok@fucape.br"] == "ok"
