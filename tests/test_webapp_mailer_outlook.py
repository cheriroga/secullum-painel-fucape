import pytest

from webapp import mailer_outlook
from webapp.mensagem_email import CAMINHO_ASSINATURA, CID_ASSINATURA


class _FakePropertyAccessor:
    def __init__(self):
        self.propriedades = {}

    def SetProperty(self, nome, valor):
        self.propriedades[nome] = valor


class _FakeAttachment:
    def __init__(self, caminho):
        self.caminho = caminho
        self.PropertyAccessor = _FakePropertyAccessor()


class _FakeAttachments:
    def __init__(self):
        self.itens = []

    def Add(self, caminho):
        anexo = _FakeAttachment(caminho)
        self.itens.append(anexo)
        return anexo


class _FakeMailItem:
    def __init__(self):
        self.To = None
        self.Subject = None
        self.HTMLBody = None
        self.Attachments = _FakeAttachments()
        self.enviado = False
        self.conta_usada = None

    def Send(self):
        self.enviado = True


class _FakeAccount:
    def __init__(self, smtp):
        self.SmtpAddress = smtp
        self.DisplayName = smtp


class _FakeAccounts:
    def __init__(self, smtps):
        self._contas = [_FakeAccount(s) for s in smtps]

    @property
    def Count(self):
        return len(self._contas)

    def Item(self, i):  # coleção COM é 1-based
        return self._contas[i - 1]


class _FakeSession:
    def __init__(self, smtps):
        self.Accounts = _FakeAccounts(smtps)


# Espelha a máquina real: duas contas, a padrão (Item 1) NÃO é a kristielle.
_CONTAS_PADRAO = ["nathalianunes@fucape.br", "kristielledantas@fucape.br"]


class _FakeOutlookApp:
    def __init__(self, smtps=_CONTAS_PADRAO):
        self.itens_criados = []
        self.Session = _FakeSession(smtps)

    def CreateItem(self, tipo_item):
        item = _FakeMailItem()
        self.itens_criados.append(item)
        return item


@pytest.fixture(autouse=True)
def _mock_send_using_account(monkeypatch):
    # _usar_conta usa Invoke de baixo nível (email._oleobj_), que os fakes não
    # têm — registra a conta escolhida no item pra dar pra checar.
    monkeypatch.setattr(
        mailer_outlook, "_usar_conta",
        lambda email, conta: setattr(email, "conta_usada", conta),
    )


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


def test_enviar_notificacao_anexa_assinatura_inline_com_cid(monkeypatch):
    app_falso = _FakeOutlookApp()
    monkeypatch.setattr(mailer_outlook.win32com.client, "Dispatch", lambda nome: app_falso)

    mailer_outlook.enviar_notificacao({"ceo@fucape.br": "https://x/2026-06/"}, "Junho/2026")

    item = app_falso.itens_criados[0]
    assert len(item.Attachments.itens) == 1
    anexo = item.Attachments.itens[0]
    assert anexo.caminho == str(CAMINHO_ASSINATURA)
    assert anexo.PropertyAccessor.propriedades[mailer_outlook.PROPRIEDADE_MAPI_CID] == CID_ASSINATURA


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
            self.Session = _FakeSession(_CONTAS_PADRAO)

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


def test_enviar_notificacao_usa_a_conta_do_remetente_configurado(monkeypatch):
    app_falso = _FakeOutlookApp()
    monkeypatch.setattr(mailer_outlook.win32com.client, "Dispatch", lambda nome: app_falso)

    mailer_outlook.enviar_notificacao(
        {"ceo@fucape.br": "https://x/2026-06/"}, "Junho/2026",
        remetente="kristielledantas@fucape.br",
    )

    item = app_falso.itens_criados[0]
    assert item.conta_usada is not None
    assert item.conta_usada.SmtpAddress == "kristielledantas@fucape.br"


def test_enviar_notificacao_remetente_default_e_kristielle_nao_a_conta_padrao(monkeypatch):
    app_falso = _FakeOutlookApp()
    monkeypatch.setattr(mailer_outlook.win32com.client, "Dispatch", lambda nome: app_falso)

    # sem passar remetente -> usa REMETENTE_PADRAO; NÃO pode cair na conta padrão
    # do perfil (Item 1 = nathalianunes).
    mailer_outlook.enviar_notificacao({"ceo@fucape.br": "https://x/2026-06/"}, "Junho/2026")

    assert app_falso.itens_criados[0].conta_usada.SmtpAddress == "kristielledantas@fucape.br"


def test_enviar_notificacao_conta_inexistente_levanta_envio_error(monkeypatch):
    app_falso = _FakeOutlookApp(smtps=["nathalianunes@fucape.br"])  # sem kristielle
    monkeypatch.setattr(mailer_outlook.win32com.client, "Dispatch", lambda nome: app_falso)

    with pytest.raises(mailer_outlook.EnvioError):
        mailer_outlook.enviar_notificacao({"ceo@fucape.br": "https://x/"}, "Junho/2026")
