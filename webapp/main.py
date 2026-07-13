import os
import shutil
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from webapp import config as config_mod
from webapp import deploy_netlify, mailer_graph
from webapp.pipeline import processar_upload

RAIZ = Path(__file__).resolve().parent.parent
PASTA_BASE = RAIZ / "painel_web"
PASTA_UPLOADS = RAIZ / "webapp_data" / "uploads"
CAMINHO_CONFIG = RAIZ / "webapp_data" / "config.json"

app = FastAPI()

ESTADO: dict = {}

PASTA_BASE.mkdir(parents=True, exist_ok=True)
app.mount("/painel", StaticFiles(directory=str(PASTA_BASE)), name="painel")

@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return """
    <html><body>
    <h1>Painel de horas</h1>
    <form action="/upload" method="post" enctype="multipart/form-data">
      <input type="file" name="arquivo" accept=".xlsx" required>
      <button type="submit">Enviar arquivo</button>
    </form>
    </body></html>
    """


@app.post("/upload", response_class=HTMLResponse, response_model=None)
async def upload(arquivo: UploadFile = File(...)) -> HTMLResponse | RedirectResponse:
    PASTA_UPLOADS.mkdir(parents=True, exist_ok=True)
    destino = PASTA_UPLOADS / Path(arquivo.filename).name
    with destino.open("wb") as saida:
        shutil.copyfileobj(arquivo.file, saida)

    try:
        resumo = processar_upload(destino, PASTA_BASE)
    except ValueError as erro:
        return HTMLResponse(f"""
        <html><body>
        <h1>Não deu pra processar o arquivo</h1>
        <p>{erro}</p>
        <a href="/">Tentar de novo</a>
        </body></html>
        """)

    ESTADO["ultimo"] = resumo
    return RedirectResponse("/preview", status_code=303)


@app.get("/preview", response_class=HTMLResponse, response_model=None)
def preview() -> HTMLResponse | RedirectResponse:
    resumo = ESTADO.get("ultimo")
    if not resumo:
        return RedirectResponse("/", status_code=303)

    mapa = config_mod.carregar_config(CAMINHO_CONFIG)
    deptos = sorted(set(mapa) | set(resumo["departamentos_labels"]))
    linhas_config = "".join(
        f'<div>{depto}: <input name="email_{depto}" value="{mapa.get(depto, "")}"></div>'
        for depto in deptos
    )
    faltando = [depto for depto in resumo["departamentos_labels"] if not mapa.get(depto)]
    aviso_faltando = "".join(
        f"<p style='color:orange'>{depto}: sem e-mail de gestor configurado — esse departamento "
        "não vai receber notificação se você enviar agora.</p>"
        for depto in faltando
    )

    return HTMLResponse(f"""
    <html><body>
    <h1>Painel gerado — período {resumo['periodo']}</h1>
    <p>{resumo['colaboradores']} colaboradores · {resumo['departamentos']} departamentos ·
       {resumo['elegiveis']} elegíveis · {resumo['nao_elegiveis']} fora da base</p>
    <iframe src="/painel/{resumo['periodo']}/index.html" width="100%" height="600"></iframe>

    <form action="/config" method="post">
      <h2>Gestores por departamento</h2>
      {linhas_config}
      <button type="submit">Salvar configuração</button>
    </form>

    {aviso_faltando}

    <form action="/enviar" method="post"
          onsubmit="return confirm('Confirma a publicação e o envio de e-mail?')">
      <button type="submit">Enviar</button>
    </form>
    </body></html>
    """)


@app.post("/config")
async def salvar_config_route(request: Request) -> RedirectResponse:
    formulario = await request.form()
    mapa = {}
    for chave, valor in formulario.items():
        if chave.startswith("email_") and str(valor).strip():
            depto = chave[len("email_"):]
            mapa[depto] = str(valor).strip()
    config_mod.salvar_config(CAMINHO_CONFIG, mapa)
    return RedirectResponse("/preview", status_code=303)


def _renderizar_resultado(link: str, resultados: dict[str, str]) -> HTMLResponse:
    falhas = {destinatario: msg for destinatario, msg in resultados.items() if msg != "ok"}
    linhas = "".join(f"<li>{destinatario}: {msg}</li>" for destinatario, msg in resultados.items())

    if falhas:
        aviso = f"<p style='color:red'>{len(falhas)} envio(s) falharam.</p>"
        botao_retry = """
        <form action="/reenviar" method="post">
          <button type="submit">Reenviar só pra quem falhou</button>
        </form>
        """
    else:
        aviso = "<p>Todos os envios OK.</p>"
        botao_retry = ""

    return HTMLResponse(f"""
    <html><body>
    <h1>Publicado em {link}</h1>
    {aviso}
    <ul>{linhas}</ul>
    {botao_retry}
    <a href="/preview">Voltar</a>
    </body></html>
    """)


VARIAVEIS_OBRIGATORIAS = ("PAINEL_CEO_EMAIL", "GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET")


@app.post("/enviar", response_class=HTMLResponse, response_model=None)
def enviar() -> HTMLResponse | RedirectResponse:
    resumo = ESTADO.get("ultimo")
    if not resumo:
        return RedirectResponse("/", status_code=303)

    for nome_variavel in VARIAVEIS_OBRIGATORIAS:
        if not os.environ.get(nome_variavel):
            return HTMLResponse(f"""
            <html><body>
            <h1>Falta configurar variável de ambiente: {nome_variavel}</h1>
            <a href="/preview">Voltar</a>
            </body></html>
            """)

    ceo_email = os.environ["PAINEL_CEO_EMAIL"]
    tenant_id = os.environ["GRAPH_TENANT_ID"]
    client_id = os.environ["GRAPH_CLIENT_ID"]
    client_secret = os.environ["GRAPH_CLIENT_SECRET"]

    try:
        url_site = deploy_netlify.publicar(PASTA_BASE)
    except deploy_netlify.DeployError as erro:
        return HTMLResponse(f"""
        <html><body>
        <h1>Falha ao publicar</h1>
        <p>{erro}</p>
        <a href="/preview">Voltar</a>
        </body></html>
        """)

    mapa = config_mod.carregar_config(CAMINHO_CONFIG)
    destinatarios = list(dict.fromkeys([ceo_email] + list(mapa.values())))

    link = f"{url_site}/{resumo['periodo']}/"

    try:
        token = mailer_graph.obter_token(tenant_id, client_id, client_secret)
    except mailer_graph.EnvioError as erro:
        resultados = {
            destinatario: f"erro: falha de autenticação Graph — {erro}" for destinatario in destinatarios
        }
        ESTADO["ultima_publicacao"] = {"link": link, "periodo": resumo["periodo"], "resultados": resultados}
        return _renderizar_resultado(link, resultados)

    remetente = os.environ.get("GRAPH_REMETENTE", "relatorios@fucape.br")
    resultados = mailer_graph.enviar_notificacao(token, remetente, destinatarios, resumo["periodo"], link)

    ESTADO["ultima_publicacao"] = {"link": link, "periodo": resumo["periodo"], "resultados": resultados}
    return _renderizar_resultado(link, resultados)


@app.post("/reenviar", response_class=HTMLResponse, response_model=None)
def reenviar() -> HTMLResponse | RedirectResponse:
    publicacao = ESTADO.get("ultima_publicacao")
    if not publicacao:
        return RedirectResponse("/", status_code=303)

    destinatarios_com_falha = [
        destinatario for destinatario, msg in publicacao["resultados"].items() if msg != "ok"
    ]

    try:
        token = mailer_graph.obter_token(
            os.environ["GRAPH_TENANT_ID"], os.environ["GRAPH_CLIENT_ID"], os.environ["GRAPH_CLIENT_SECRET"],
        )
    except mailer_graph.EnvioError as erro:
        publicacao["resultados"].update({
            destinatario: f"erro: falha de autenticação Graph — {erro}"
            for destinatario in destinatarios_com_falha
        })
        return _renderizar_resultado(publicacao["link"], publicacao["resultados"])

    remetente = os.environ.get("GRAPH_REMETENTE", "relatorios@fucape.br")
    novos_resultados = mailer_graph.enviar_notificacao(
        token, remetente, destinatarios_com_falha, publicacao["periodo"], publicacao["link"],
    )

    publicacao["resultados"].update(novos_resultados)
    return _renderizar_resultado(publicacao["link"], publicacao["resultados"])
