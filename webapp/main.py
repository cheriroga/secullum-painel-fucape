import shutil
from pathlib import Path

from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from webapp import config as config_mod
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
    destino = PASTA_UPLOADS / arquivo.filename
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
