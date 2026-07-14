import os
import shutil
import threading
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from painel_horas.slug import slugify
from webapp import config as config_mod
from webapp import deploy_netlify, mailer_graph
from webapp.pipeline import processar_upload

load_dotenv()

RAIZ = Path(__file__).resolve().parent.parent
PASTA_BASE = RAIZ / "painel_web"
PASTA_UPLOADS = RAIZ / "webapp_data" / "uploads"
CAMINHO_CONFIG = RAIZ / "webapp_data" / "config.json"

app = FastAPI()

ESTADO: dict = {}

ESTILO = """
<style>
:root{--bg:#0b0f14;--panel:#121821;--panel2:#0e141c;--line:#1f2933;--ink:#e8edf2;--mut:#8a97a6;--pos:#3ddc84;--neg:#ff5c5c;--amber:#ffb020;--blue:#4da3ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:720px;margin:0 auto;padding:32px 24px 64px}
.eyebrow{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);margin-bottom:6px}
h1{margin:0 0 20px;font-size:22px;font-weight:800}
h2{font-size:15px;margin:0 0 4px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:20px;margin-bottom:20px}
.muted{color:var(--mut);font-size:12.5px;margin:0 0 14px}
.row{display:flex;align-items:center;gap:12px;padding:8px 0;border-bottom:1px solid var(--line)}
.row:last-child{border-bottom:none}
.row label{flex:1;font-size:13px;min-width:0}
input[type=email],input[type=text],input[type=file]{background:var(--panel2);border:1px solid var(--line);color:var(--ink);border-radius:6px;padding:8px 10px;font-size:13px;flex:1;font-family:inherit}
.row input[type=email]{flex:0 0 220px;max-width:220px}
input:focus{outline:none;border-color:var(--blue)}
button{background:var(--blue);color:#04101f;border:none;border-radius:6px;padding:10px 18px;font-size:13px;font-weight:700;cursor:pointer;font-family:inherit}
button:hover{opacity:.9}
.btn-secondary{background:var(--panel2);color:var(--ink);border:1px solid var(--line)}
a{color:var(--blue)}
iframe{border:1px solid var(--line);border-radius:8px;background:#fff;display:block}
.warn{background:#2a2410;border:1px solid #4d3f12;color:#e8dcae;border-radius:8px;padding:10px 14px;font-size:12.5px;margin-bottom:10px}
.badge-warn{background:#2a2410;border:1px solid #4d3f12;color:var(--amber);font-size:10px;font-weight:600;padding:2px 8px;border-radius:20px;margin-left:8px}
.row-buttons{display:flex;justify-content:flex-end;gap:12px;margin-top:16px}
.card.ok{border-left:3px solid var(--pos)}
.card.err{border-left:3px solid var(--neg)}
ul.resultados{list-style:none;padding:0;margin:0}
ul.resultados li{padding:6px 0;border-bottom:1px solid var(--line);font-size:13px}
ul.resultados li:last-child{border-bottom:none}
</style>
<script>
setInterval(() => { fetch('/heartbeat', {method: 'POST'}).catch(() => {}) }, 4000);
</script>
"""

PASTA_BASE.mkdir(parents=True, exist_ok=True)
app.mount("/painel", StaticFiles(directory=str(PASTA_BASE)), name="painel")

ULTIMO_HEARTBEAT = {"quando": time.monotonic()}


@app.post("/heartbeat")
def heartbeat() -> dict:
    ULTIMO_HEARTBEAT["quando"] = time.monotonic()
    return {"ok": True}


def iniciar_monitor_heartbeat(timeout_segundos: int = 20) -> None:
    """Inicia uma thread em segundo plano que encerra o processo se
    nenhum heartbeat chegar por timeout_segundos — assim o servidor
    fecha sozinho quando a pessoa fecha a aba do navegador, sem depender
    dela lembrar de fechar o terminal. Não é chamada na importação do
    módulo (só pelo entry point real), pra nunca matar o processo de
    testes que importa este módulo sem nunca mandar heartbeat."""
    def _monitorar() -> None:
        while True:
            time.sleep(2)
            if time.monotonic() - ULTIMO_HEARTBEAT["quando"] > timeout_segundos:
                os._exit(0)

    threading.Thread(target=_monitorar, daemon=True).start()

@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return f"""
    <html><head><meta charset="UTF-8"><title>Painel de horas · Fucape</title>{ESTILO}</head><body>
    <div class="wrap">
      <div class="eyebrow">Fucape Business School · Cartão Ponto Secullum</div>
      <h1>Painel de horas</h1>
      <div class="card">
        <form action="/upload" method="post" enctype="multipart/form-data">
          <div class="row">
            <label>Arquivo (.xlsx)</label>
            <input type="file" name="arquivo" accept=".xlsx" required>
          </div>
          <button type="submit">Enviar arquivo</button>
        </form>
      </div>
    </div>
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
        <html><head><meta charset="UTF-8"><title>Erro · Fucape</title>{ESTILO}</head><body>
        <div class="wrap">
          <h1>Não deu pra processar o arquivo</h1>
          <div class="card err">{erro}</div>
          <a href="/">Tentar de novo</a>
        </div>
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
        f'<div class="row"><label>{depto}'
        + ('' if mapa.get(depto) else ' <span class="badge-warn">sem e-mail</span>')
        + '</label>'
        f'<input type="email" name="email_{depto}" value="{mapa.get(depto, "")}" '
        f'placeholder="email do gestor"></div>'
        for depto in deptos
    )

    return HTMLResponse(f"""
    <html><head><meta charset="UTF-8"><title>Painel gerado · Fucape</title>{ESTILO}</head><body>
    <div class="wrap">
      <div class="eyebrow">Fucape Business School · Cartão Ponto Secullum</div>
      <h1>Painel gerado — período {resumo['periodo']}</h1>
      <p class="muted">{resumo['colaboradores']} colaboradores · {resumo['departamentos']} departamentos ·
         {resumo['elegiveis']} elegíveis · {resumo['nao_elegiveis']} fora da base</p>

      <div class="card">
        <iframe src="/painel/{resumo['periodo']}/index.html" width="100%" height="600"></iframe>
      </div>

      <div class="card">
        <h2>Gestores por departamento</h2>
        <p class="muted">Já configurado? Pode trocar o e-mail a qualquer momento — só editar o campo e salvar de novo.</p>
        <form id="form-gestores" method="post">
          {linhas_config}
        </form>
        <div class="row-buttons">
          <button type="submit" form="form-gestores" formaction="/config" class="btn-secondary">Salvar configuração</button>
          <button type="submit" form="form-gestores" formaction="/enviar"
                  onclick="return confirm('Confirma a publicação e o envio de e-mail?')">Enviar</button>
        </div>
      </div>
    </div>
    </body></html>
    """)


def _extrair_mapa_do_formulario(formulario) -> dict[str, str]:
    mapa = {}
    for chave, valor in formulario.items():
        if chave.startswith("email_") and str(valor).strip():
            depto = chave[len("email_"):]
            mapa[depto] = str(valor).strip()
    return mapa


@app.post("/config")
async def salvar_config_route(request: Request) -> RedirectResponse:
    mapa = _extrair_mapa_do_formulario(await request.form())
    config_mod.salvar_config(CAMINHO_CONFIG, mapa)
    return RedirectResponse("/preview", status_code=303)


def _renderizar_resultado(link_geral: str, resultados: dict[str, str], links: dict[str, str]) -> HTMLResponse:
    falhas = {destinatario: msg for destinatario, msg in resultados.items() if msg != "ok"}
    linhas = "".join(
        f"<li>{destinatario}: {msg} — <a href=\"{links.get(destinatario, '')}\">{links.get(destinatario, '')}</a></li>"
        for destinatario, msg in resultados.items()
    )

    if falhas:
        classe_card = "err"
        aviso = f"{len(falhas)} envio(s) falharam."
        botao_retry = """
        <form action="/reenviar" method="post">
          <button type="submit" class="btn-secondary">Reenviar só pra quem falhou</button>
        </form>
        """
    else:
        classe_card = "ok"
        aviso = "Todos os envios OK."
        botao_retry = ""

    aviso_modo_teste = (
        "<div class='warn'>Modo teste ativo (PAINEL_MODO_TESTE) — nada foi publicado no Netlify "
        "nem enviado por e-mail de verdade.</div>"
        if os.environ.get("PAINEL_MODO_TESTE") else ""
    )

    return HTMLResponse(f"""
    <html><head><meta charset="UTF-8"><title>Resultado do envio · Fucape</title>{ESTILO}</head><body>
    <div class="wrap">
      <h1>Publicado em <a href="{link_geral}">{link_geral}</a></h1>
      {aviso_modo_teste}
      <div class="card {classe_card}">{aviso}</div>
      <div class="card"><ul class="resultados">{linhas}</ul></div>
      {botao_retry}
      <a href="/preview">Voltar</a>
    </div>
    </body></html>
    """)


VARIAVEIS_OBRIGATORIAS = ("PAINEL_CEO_EMAIL", "GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET")


@app.post("/enviar", response_class=HTMLResponse, response_model=None)
async def enviar(request: Request) -> HTMLResponse | RedirectResponse:
    resumo = ESTADO.get("ultimo")
    if not resumo:
        return RedirectResponse("/", status_code=303)

    mapa = _extrair_mapa_do_formulario(await request.form())
    config_mod.salvar_config(CAMINHO_CONFIG, mapa)

    for nome_variavel in VARIAVEIS_OBRIGATORIAS:
        if not os.environ.get(nome_variavel):
            return HTMLResponse(f"""
            <html><head><meta charset="UTF-8"><title>Erro · Fucape</title>{ESTILO}</head><body>
            <div class="wrap">
              <h1>Falta configurar variável de ambiente</h1>
              <div class="card err">{nome_variavel}</div>
              <a href="/preview">Voltar</a>
            </div>
            </body></html>
            """)

    ceo_email = os.environ["PAINEL_CEO_EMAIL"]
    tenant_id = os.environ["GRAPH_TENANT_ID"]
    client_id = os.environ["GRAPH_CLIENT_ID"]
    client_secret = os.environ["GRAPH_CLIENT_SECRET"]
    modo_teste = bool(os.environ.get("PAINEL_MODO_TESTE"))

    if modo_teste:
        url_site = "https://modo-teste.invalido"
    else:
        try:
            url_site = deploy_netlify.publicar(PASTA_BASE)
        except deploy_netlify.DeployError as erro:
            return HTMLResponse(f"""
            <html><head><meta charset="UTF-8"><title>Erro · Fucape</title>{ESTILO}</head><body>
            <div class="wrap">
              <h1>Falha ao publicar</h1>
              <div class="card err">{erro}</div>
              <a href="/preview">Voltar</a>
            </div>
            </body></html>
            """)

    link_geral = f"{url_site}/{resumo['periodo']}/"

    destinatarios_links = {
        email: f"{link_geral}deptos/{slugify(depto)}.html" for depto, email in mapa.items()
    }
    destinatarios_links[ceo_email] = link_geral  # CEO sempre recebe o painel geral, mesmo se também for gestor

    if modo_teste:
        resultados = {destinatario: "ok" for destinatario in destinatarios_links}
    else:
        try:
            token = mailer_graph.obter_token(tenant_id, client_id, client_secret)
        except mailer_graph.EnvioError as erro:
            resultados = {
                destinatario: f"erro: falha de autenticação Graph — {erro}" for destinatario in destinatarios_links
            }
            ESTADO["ultima_publicacao"] = {
                "link_geral": link_geral, "periodo": resumo["periodo"], "periodo_extenso": resumo["periodo_extenso"],
                "resultados": resultados, "links": destinatarios_links,
            }
            return _renderizar_resultado(link_geral, resultados, destinatarios_links)

        remetente = os.environ.get("GRAPH_REMETENTE", "relatorios@fucape.br")
        resultados = mailer_graph.enviar_notificacao(
            token, remetente, destinatarios_links, resumo["periodo_extenso"],
        )

    ESTADO["ultima_publicacao"] = {
        "link_geral": link_geral, "periodo": resumo["periodo"], "periodo_extenso": resumo["periodo_extenso"],
        "resultados": resultados, "links": destinatarios_links,
    }
    return _renderizar_resultado(link_geral, resultados, destinatarios_links)


@app.post("/reenviar", response_class=HTMLResponse, response_model=None)
def reenviar() -> HTMLResponse | RedirectResponse:
    publicacao = ESTADO.get("ultima_publicacao")
    if not publicacao:
        return RedirectResponse("/", status_code=303)

    destinatarios_com_falha = [
        destinatario for destinatario, msg in publicacao["resultados"].items() if msg != "ok"
    ]
    links_com_falha = {destinatario: publicacao["links"][destinatario] for destinatario in destinatarios_com_falha}

    if bool(os.environ.get("PAINEL_MODO_TESTE")):
        novos_resultados = {destinatario: "ok" for destinatario in destinatarios_com_falha}
    else:
        try:
            token = mailer_graph.obter_token(
                os.environ["GRAPH_TENANT_ID"], os.environ["GRAPH_CLIENT_ID"], os.environ["GRAPH_CLIENT_SECRET"],
            )
        except mailer_graph.EnvioError as erro:
            publicacao["resultados"].update({
                destinatario: f"erro: falha de autenticação Graph — {erro}"
                for destinatario in destinatarios_com_falha
            })
            return _renderizar_resultado(publicacao["link_geral"], publicacao["resultados"], publicacao["links"])

        remetente = os.environ.get("GRAPH_REMETENTE", "relatorios@fucape.br")
        novos_resultados = mailer_graph.enviar_notificacao(
            token, remetente, links_com_falha, publicacao["periodo_extenso"],
        )

    publicacao["resultados"].update(novos_resultados)
    return _renderizar_resultado(publicacao["link_geral"], publicacao["resultados"], publicacao["links"])
