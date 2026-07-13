import shutil
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from webapp.pipeline import processar_upload

RAIZ = Path(__file__).resolve().parent.parent
PASTA_BASE = RAIZ / "painel_web"
PASTA_UPLOADS = RAIZ / "webapp_data" / "uploads"

app = FastAPI()

ESTADO: dict = {}


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
