# Protótipo local: app web + deploy Netlify + envio por Graph API — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local FastAPI app that lets the Secullum-responsible person upload the `cartaoponto.xlsx`, preview the generated panel, and click one button to publish it to Netlify and notify the CEO + department managers by email via Microsoft Graph API.

**Architecture:** A new `webapp/` package wraps the existing, unchanged `painel_horas/` pipeline (via `atualizar_painel.gerar_painel`) with a period-scoped output folder, a department→manager email config store, a Netlify CLI wrapper, and a Microsoft Graph `sendMail` wrapper. A thin FastAPI app (server-rendered HTML, no JS framework, no build step — same "no external assets" spirit as the existing Jinja2 templates) wires upload → preview → send into one page flow, held in a single in-memory state dict (single local user, no concurrency to handle).

**Tech Stack:** Python 3.10+, FastAPI + uvicorn (web server), python-multipart (file upload parsing), httpx (required by FastAPI's `TestClient`), msal (Microsoft Graph OAuth client-credentials token), requests (HTTP calls to Graph API), Netlify CLI (external tool, invoked via `subprocess` — not a pip package), pytest + `monkeypatch` (mocking subprocess/HTTP in tests, no real Netlify/Graph calls in the test suite).

## Global Constraints

- Reuse `painel_horas/` (parser, calculos, template) and `atualizar_painel.gerar_painel` **without modifying their logic** — this prototype only wraps them.
- Windows environment — always build paths with `pathlib.Path`, never hardcode `/` separators in code (Jinja2 template `href` attributes with forward slashes are fine, those are URLs, not filesystem paths).
- No external JS/CSS frameworks and no build step for any new page, consistent with the existing `templates/*.j2` style — plain inline HTML/CSS is enough for this internal prototype.
- No authentication in front of the local app or the published Netlify site in this prototype (per spec's "Fora de escopo") — do not add login screens.
- Real Netlify/Graph API calls are never made from the automated test suite — every external call (`subprocess.run` for Netlify CLI, `requests.post`/token acquisition for Graph) must be monkeypatched in tests.
- Secrets (Netlify token, Graph client secret) come from environment variables, never hardcoded or committed.

---

### Task 1: Period slug helper

**Files:**
- Create: `webapp/__init__.py`
- Create: `webapp/periodo.py`
- Test: `tests/test_webapp_periodo.py`

**Interfaces:**
- Consumes: `painel_horas.parser.Colaborador`, `painel_horas.parser.Dia` (existing dataclasses — `Colaborador.dias: list[Dia]`, `Dia.data: date`).
- Produces: `periodo_slug(colaboradores: list[Colaborador]) -> str` — returns e.g. `"2026-06"` (the year-month of the earliest date found across all `dias`). Raises `ValueError` if no dates are found. Used by Task 3's `pipeline.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_webapp_periodo.py`:

```python
import datetime

import pytest

from painel_horas.parser import Colaborador, Dia
from webapp.periodo import periodo_slug


def _dia(data_str):
    ano, mes, dia = map(int, data_str.split("-"))
    return Dia(
        data=datetime.date(ano, mes, dia), dia_semana="Qui",
        ent1=None, sai1=None, ent2=None, sai2=None, ent3=None, sai3=None,
        ex50_min=0, atraso_min=0, btotal_min=0, exnot_min=0,
    )


def test_periodo_slug_usa_ano_mes_da_data_mais_antiga():
    colaboradores = [
        Colaborador(
            nome="A", funcao="X", admissao=None, departamento="TI",
            dias=[_dia("2026-06-15"), _dia("2026-06-30")],
        ),
        Colaborador(
            nome="B", funcao="X", admissao=None, departamento="TI",
            dias=[_dia("2026-06-01")],
        ),
    ]
    assert periodo_slug(colaboradores) == "2026-06"


def test_periodo_slug_sem_dias_registrados_leva_a_erro():
    colaboradores = [Colaborador(nome="A", funcao="X", admissao=None, departamento="TI", dias=[])]
    with pytest.raises(ValueError):
        periodo_slug(colaboradores)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_webapp_periodo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webapp'`

- [ ] **Step 3: Write minimal implementation**

Create `webapp/__init__.py` (empty file).

Create `webapp/periodo.py`:

```python
from painel_horas.parser import Colaborador


def periodo_slug(colaboradores: list[Colaborador]) -> str:
    """Retorna o período (ano-mês) da data mais antiga encontrada entre
    todos os dias de todos os colaboradores, no formato "AAAA-MM"."""
    todas_datas = [dia.data for colaborador in colaboradores for dia in colaborador.dias]
    if not todas_datas:
        raise ValueError("Arquivo sem dias registrados — não é possível determinar o período.")
    data_mais_antiga = min(todas_datas)
    return data_mais_antiga.strftime("%Y-%m")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_webapp_periodo.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add webapp/__init__.py webapp/periodo.py tests/test_webapp_periodo.py
git commit -m "feat: add periodo_slug helper for webapp prototype"
```

---

### Task 2: Department → manager email config store

**Files:**
- Create: `webapp/config.py`
- Test: `tests/test_webapp_config.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: nothing new (just `pathlib.Path`, `json`).
- Produces: `carregar_config(caminho: Path) -> dict[str, str]` and `salvar_config(caminho: Path, mapa: dict[str, str]) -> None`. Used by Task 7's `/config` route and Task 8's `/enviar` route.

- [ ] **Step 1: Write the failing test**

Create `tests/test_webapp_config.py`:

```python
from webapp.config import carregar_config, salvar_config


def test_carregar_config_arquivo_inexistente_retorna_vazio(tmp_path):
    assert carregar_config(tmp_path / "config.json") == {}


def test_salvar_e_carregar_config_roundtrip(tmp_path):
    caminho = tmp_path / "sub" / "config.json"
    mapa = {"TECNOLOGIA": "gestor.ti@fucape.br", "MARKETING": "gestor.mkt@fucape.br"}

    salvar_config(caminho, mapa)

    assert carregar_config(caminho) == mapa
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_webapp_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webapp.config'`

- [ ] **Step 3: Write minimal implementation**

Create `webapp/config.py`:

```python
import json
from pathlib import Path


def carregar_config(caminho: Path) -> dict[str, str]:
    """Carrega o mapa departamento -> e-mail do gestor. Retorna {} se o
    arquivo ainda não existir (primeira execução)."""
    if not caminho.exists():
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))


def salvar_config(caminho: Path, mapa: dict[str, str]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(mapa, ensure_ascii=False, indent=2), encoding="utf-8")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_webapp_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Ignore the runtime data folder**

Append to `.gitignore`:

```
webapp_data/
```

- [ ] **Step 6: Commit**

```bash
git add webapp/config.py tests/test_webapp_config.py .gitignore
git commit -m "feat: add department-to-manager email config store"
```

---

### Task 3: Upload pipeline (wraps existing gerar_painel per period)

**Files:**
- Create: `webapp/pipeline.py`
- Test: `tests/test_webapp_pipeline.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `webapp.periodo.periodo_slug` (Task 1), `atualizar_painel.gerar_painel(caminho_xlsx: Path, pasta_saida: Path) -> dict` (existing, returns `{"colaboradores": int, "departamentos": int, "elegiveis": int, "nao_elegiveis": int}`), `painel_horas.parser.ler_colaboradores`, `painel_horas.calculos.dept_label`.
- Produces: `processar_upload(caminho_xlsx: Path, pasta_base: Path) -> dict` returning:
  ```python
  {
      "periodo": str,               # e.g. "2026-06"
      "pasta": Path,                 # pasta_base / periodo
      "colaboradores": int,
      "departamentos": int,
      "elegiveis": int,
      "nao_elegiveis": int,
      "departamentos_labels": list[str],  # sorted, e.g. ["Centro de Serviços Compartilhados", "Tecnologia"]
  }
  ```
  Raises `ValueError` if the file has no recognizable collaborators. Used by Task 6's `/upload` route and Task 7's `/preview`/`/config` routes.

- [ ] **Step 1: Write the failing test**

Create `tests/test_webapp_pipeline.py` (reuses the `workbook_path` fixture already defined in `tests/conftest.py`):

```python
import datetime

import pytest

from webapp.pipeline import processar_upload


def _dia_com_batida(data_str, btotal_str):
    return (data_str, "Qui", datetime.timedelta(hours=8), datetime.timedelta(hours=17),
            None, None, None, None, None, None, btotal_str, None)


def test_processar_upload_gera_painel_em_pasta_do_periodo(tmp_path, workbook_path):
    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    pasta_base = tmp_path / "painel_web"

    resultado = processar_upload(caminho, pasta_base)

    assert resultado["periodo"] == "2026-06"
    assert resultado["pasta"] == pasta_base / "2026-06"
    assert resultado["colaboradores"] == 1
    assert resultado["departamentos_labels"] == ["Tecnologia"]
    assert (pasta_base / "2026-06" / "index.html").exists()


def test_processar_upload_sem_colaboradores_reconheciveis_leva_a_erro(tmp_path, workbook_path):
    caminho = workbook_path([])
    pasta_base = tmp_path / "painel_web"

    with pytest.raises(ValueError):
        processar_upload(caminho, pasta_base)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_webapp_pipeline.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webapp.pipeline'`

- [ ] **Step 3: Write minimal implementation**

Create `webapp/pipeline.py`:

```python
from pathlib import Path

from atualizar_painel import gerar_painel
from painel_horas.calculos import dept_label
from painel_horas.parser import ler_colaboradores
from webapp.periodo import periodo_slug


def processar_upload(caminho_xlsx: Path, pasta_base: Path) -> dict:
    colaboradores = ler_colaboradores(caminho_xlsx)
    if not colaboradores:
        raise ValueError("Nenhum colaborador reconhecido no arquivo enviado.")

    periodo = periodo_slug(colaboradores)
    pasta_periodo = pasta_base / periodo
    resumo = gerar_painel(caminho_xlsx, pasta_periodo)
    departamentos_labels = sorted({dept_label(c.departamento) for c in colaboradores})

    return {
        "periodo": periodo,
        "pasta": pasta_periodo,
        "departamentos_labels": departamentos_labels,
        **resumo,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_webapp_pipeline.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Ignore the generated web output folder**

Append to `.gitignore`:

```
painel_web/
```

- [ ] **Step 6: Commit**

```bash
git add webapp/pipeline.py tests/test_webapp_pipeline.py .gitignore
git commit -m "feat: add upload pipeline that generates the panel per period"
```

---

### Task 4: Netlify deploy wrapper

**Files:**
- Create: `webapp/deploy_netlify.py`
- Test: `tests/test_webapp_deploy_netlify.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (only `pathlib.Path`, `subprocess`, `json`).
- Produces: `publicar(pasta_base: Path) -> str` (returns the site's base URL, no trailing slash, e.g. `"https://painel-fucape.netlify.app"`) and `DeployError` exception class. Used by Task 8's `/enviar` route. **Important:** `pasta_base` must be the whole accumulated output root (containing every period subfolder generated so far), not just the newest period — this is what keeps previously-published period links alive across deploys, since Netlify re-uploads the full directory tree every time.

- [ ] **Step 1: Write the failing test**

Create `tests/test_webapp_deploy_netlify.py`:

```python
import subprocess

import pytest

from webapp import deploy_netlify


def test_publicar_retorna_url_sem_barra_final(tmp_path, monkeypatch):
    def fake_run(comando, capture_output, text):
        assert comando[:3] == ["netlify", "deploy", "--prod"]
        assert str(tmp_path) in comando
        return subprocess.CompletedProcess(
            comando, returncode=0, stdout='{"deploy_url": "https://painel-fucape.netlify.app/"}', stderr="",
        )

    monkeypatch.setattr(deploy_netlify.subprocess, "run", fake_run)

    url = deploy_netlify.publicar(tmp_path)

    assert url == "https://painel-fucape.netlify.app"


def test_publicar_com_falha_do_cli_levanta_deploy_error(tmp_path, monkeypatch):
    def fake_run(comando, capture_output, text):
        return subprocess.CompletedProcess(comando, returncode=1, stdout="", stderr="not authenticated")

    monkeypatch.setattr(deploy_netlify.subprocess, "run", fake_run)

    with pytest.raises(deploy_netlify.DeployError):
        deploy_netlify.publicar(tmp_path)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_webapp_deploy_netlify.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webapp.deploy_netlify'`

- [ ] **Step 3: Write minimal implementation**

Create `webapp/deploy_netlify.py`:

```python
import json
import subprocess
from pathlib import Path


class DeployError(RuntimeError):
    pass


def publicar(pasta_base: Path) -> str:
    """Publica pasta_base (a raiz acumulada de todos os períodos já
    gerados) no Netlify e retorna a URL base do site, sem barra final."""
    resultado = subprocess.run(
        ["netlify", "deploy", "--prod", "--dir", str(pasta_base), "--json"],
        capture_output=True, text=True,
    )
    if resultado.returncode != 0:
        raise DeployError(f"Falha ao publicar no Netlify: {resultado.stderr.strip()}")

    dados = json.loads(resultado.stdout)
    url = dados.get("deploy_url") or dados.get("url")
    if not url:
        raise DeployError("Netlify não retornou uma URL de publicação.")
    return url.rstrip("/")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_webapp_deploy_netlify.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add webapp/deploy_netlify.py tests/test_webapp_deploy_netlify.py
git commit -m "feat: add Netlify CLI deploy wrapper"
```

---

### Task 5: Microsoft Graph email wrapper

**Files:**
- Create: `webapp/mailer_graph.py`
- Test: `tests/test_webapp_mailer_graph.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `obter_token(tenant_id: str, client_id: str, client_secret: str) -> str` — raises `EnvioError` if authentication fails.
  - `enviar_notificacao(token: str, remetente: str, destinatarios: list[str], periodo: str, link: str) -> dict[str, str]` — returns `{destinatario: "ok"}` or `{destinatario: "erro: <detalhe>"}` per recipient, one Graph API call per recipient (a failure for one recipient never raises — it's recorded in the returned dict so the caller can show per-recipient status and allow retrying just the failed ones).
  - `EnvioError` exception class.

  Used by Task 8's `/enviar` route.

- [ ] **Step 1: Add new dependencies**

Append to `requirements.txt`:

```
msal>=1.28
requests>=2.31
```

Run: `pip install -r requirements.txt`

- [ ] **Step 2: Write the failing test**

Create `tests/test_webapp_mailer_graph.py`:

```python
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
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_webapp_mailer_graph.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webapp.mailer_graph'`

- [ ] **Step 4: Write minimal implementation**

Create `webapp/mailer_graph.py`:

```python
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
        resposta = requests.post(
            f"https://graph.microsoft.com/v1.0/users/{remetente}/sendMail",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
            timeout=30,
        )
        if resposta.status_code == 202:
            resultados[destinatario] = "ok"
        else:
            resultados[destinatario] = f"erro: {resposta.status_code} {resposta.text[:200]}"

    return resultados
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_webapp_mailer_graph.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add webapp/mailer_graph.py tests/test_webapp_mailer_graph.py requirements.txt
git commit -m "feat: add Microsoft Graph sendMail wrapper"
```

---

### Task 6: FastAPI app skeleton — upload page and route

**Files:**
- Create: `webapp/main.py`
- Test: `tests/test_webapp_main.py`
- Modify: `requirements.txt`

**Interfaces:**
- Consumes: `webapp.pipeline.processar_upload` (Task 3).
- Produces: FastAPI `app` object with `GET /` (upload form) and `POST /upload` (saves the file, calls `processar_upload`, stores the result in module-level `ESTADO["ultimo"]`, redirects to `/preview`). Module-level constants `RAIZ`, `PASTA_BASE`, `PASTA_UPLOADS` (all `Path`), and `ESTADO: dict` are consumed directly by Task 7 and Task 8 (same module, no need to pass them around — this is a single-process, single-user prototype).

- [ ] **Step 1: Add new dependencies**

Append to `requirements.txt`:

```
fastapi>=0.110
uvicorn>=0.29
python-multipart>=0.0.9
httpx>=0.27
```

Run: `pip install -r requirements.txt`

- [ ] **Step 2: Write the failing test**

Create `tests/test_webapp_main.py`:

```python
import datetime

from fastapi.testclient import TestClient

from webapp import main


def _dia_com_batida(data_str, btotal_str):
    return (data_str, "Qui", datetime.timedelta(hours=8), datetime.timedelta(hours=17),
            None, None, None, None, None, None, btotal_str, None)


def test_get_index_mostra_formulario_de_upload():
    client = TestClient(main.app)

    resposta = client.get("/")

    assert resposta.status_code == 200
    assert 'enctype="multipart/form-data"' in resposta.text


def test_post_upload_processa_arquivo_e_redireciona_pro_preview(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    main.ESTADO.clear()

    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    client = TestClient(main.app)

    with caminho.open("rb") as arquivo:
        resposta = client.post(
            "/upload",
            files={"arquivo": ("cartaoponto.xlsx", arquivo,
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            follow_redirects=False,
        )

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/preview"
    assert main.ESTADO["ultimo"]["periodo"] == "2026-06"
    assert (tmp_path / "painel_web" / "2026-06" / "index.html").exists()


def test_post_upload_arquivo_invalido_mostra_erro_sem_avancar(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    main.ESTADO.clear()

    caminho = workbook_path([])  # nenhum colaborador reconhecível
    client = TestClient(main.app)

    with caminho.open("rb") as arquivo:
        resposta = client.post(
            "/upload",
            files={"arquivo": ("cartaoponto.xlsx", arquivo,
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )

    assert resposta.status_code == 200
    assert "Nenhum colaborador reconhecido" in resposta.text
    assert "ultimo" not in main.ESTADO
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_webapp_main.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'webapp.main'`

- [ ] **Step 4: Write minimal implementation**

Create `webapp/main.py`:

```python
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


@app.post("/upload", response_class=HTMLResponse)
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_webapp_main.py -v`
Expected: PASS (3 passed) — note `/preview` doesn't exist yet, but the redirect test only checks the redirect response, it doesn't follow it.

- [ ] **Step 6: Commit**

```bash
git add webapp/main.py tests/test_webapp_main.py requirements.txt
git commit -m "feat: add FastAPI upload page and route"
```

---

### Task 7: Preview page and department→manager config screen

**Files:**
- Modify: `webapp/main.py`
- Modify: `tests/test_webapp_main.py`

**Interfaces:**
- Consumes: `webapp.config.carregar_config` / `salvar_config` (Task 2), `ESTADO`/`PASTA_BASE` (Task 6, same module).
- Produces: `GET /preview` (shows the summary, an iframe of the generated `index.html` served under `/painel/...`, the config form, and an "Enviar" button/form), `POST /config` (saves the department→email map from form data, redirects back to `/preview`). New module constant `CAMINHO_CONFIG: Path`. The static mount name is `"painel"` — Task 8's confirmation link text and any future task must build preview URLs as `/painel/<periodo>/index.html`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_webapp_main.py`:

```python
def test_get_preview_sem_upload_redireciona_pro_index():
    main.ESTADO.clear()
    client = TestClient(main.app)

    resposta = client.get("/preview", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"


def test_get_preview_apos_upload_mostra_resumo_e_iframe(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(main, "CAMINHO_CONFIG", tmp_path / "config.json")
    main.ESTADO.clear()

    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    client = TestClient(main.app)
    with caminho.open("rb") as arquivo:
        client.post("/upload", files={"arquivo": ("cartaoponto.xlsx", arquivo,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    resposta = client.get("/preview")

    assert resposta.status_code == 200
    assert "2026-06" in resposta.text
    assert '/painel/2026-06/index.html' in resposta.text
    assert 'name="email_Tecnologia"' in resposta.text
    assert "Tecnologia: sem e-mail de gestor configurado" in resposta.text


def test_get_preview_sem_departamento_faltando_nao_mostra_alerta(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(main, "CAMINHO_CONFIG", tmp_path / "config.json")
    main.ESTADO.clear()

    from webapp.config import salvar_config
    salvar_config(tmp_path / "config.json", {"Tecnologia": "gestor.ti@fucape.br"})

    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    client = TestClient(main.app)
    with caminho.open("rb") as arquivo:
        client.post("/upload", files={"arquivo": ("cartaoponto.xlsx", arquivo,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    resposta = client.get("/preview")

    assert "sem e-mail de gestor configurado" not in resposta.text


def test_post_config_salva_mapa_e_redireciona(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "CAMINHO_CONFIG", tmp_path / "config.json")
    client = TestClient(main.app)

    resposta = client.post(
        "/config", data={"email_Tecnologia": "gestor.ti@fucape.br", "email_Vazio": ""},
        follow_redirects=False,
    )

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/preview"
    from webapp.config import carregar_config
    assert carregar_config(tmp_path / "config.json") == {"Tecnologia": "gestor.ti@fucape.br"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_webapp_main.py -v`
Expected: FAIL — `/preview` and `/config` routes don't exist yet (404s / AttributeError on `main.CAMINHO_CONFIG`).

- [ ] **Step 3: Implement the routes**

Add to `webapp/main.py` (after the existing imports, add `Request` and the `StaticFiles`/config imports; after the existing routes, add the new ones):

```python
from fastapi import Request
from fastapi.staticfiles import StaticFiles

from webapp import config as config_mod
```

```python
CAMINHO_CONFIG = RAIZ / "webapp_data" / "config.json"

PASTA_BASE.mkdir(parents=True, exist_ok=True)
app.mount("/painel", StaticFiles(directory=str(PASTA_BASE)), name="painel")
```

```python
@app.get("/preview", response_class=HTMLResponse)
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
```

Note: mounting `StaticFiles` requires `PASTA_BASE` to exist at import time — the `PASTA_BASE.mkdir(parents=True, exist_ok=True)` line above the `app.mount(...)` call handles that (it runs once, at module import).

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_webapp_main.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add webapp/main.py tests/test_webapp_main.py
git commit -m "feat: add preview page and department-manager config screen"
```

---

### Task 8: Send button — Netlify deploy + Graph email with per-recipient error reporting

**Files:**
- Modify: `webapp/main.py`
- Modify: `tests/test_webapp_main.py`

**Interfaces:**
- Consumes: `webapp.deploy_netlify.publicar` / `DeployError` (Task 4), `webapp.mailer_graph.obter_token` / `enviar_notificacao` (Task 5), `webapp.config.carregar_config` (Task 2), `ESTADO`/`PASTA_BASE`/`CAMINHO_CONFIG` (Tasks 6-7, same module). Reads environment variables `PAINEL_CEO_EMAIL`, `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET`, and optionally `GRAPH_REMETENTE` (defaults to `"relatorios@fucape.br"`).
- Produces: `POST /enviar` — publishes to Netlify, sends the notification email to the CEO and every configured manager, stores `ESTADO["ultima_publicacao"] = {"link": str, "periodo": str, "resultados": dict[str, str]}`, and renders a result page listing per-recipient status with a "Reenviar só pra quem falhou" button when there are failures. `POST /reenviar` re-sends only to the recipients whose last recorded status wasn't `"ok"`, without re-deploying to Netlify, and merges the new results into `ESTADO["ultima_publicacao"]["resultados"]`. These are the last routes in the prototype; no later task builds on them.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_webapp_main.py`:

```python
def test_post_enviar_sem_upload_redireciona_pro_index():
    main.ESTADO.clear()
    client = TestClient(main.app)

    resposta = client.post("/enviar", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"


def test_post_enviar_publica_e_notifica_com_sucesso(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(main, "CAMINHO_CONFIG", tmp_path / "config.json")
    main.ESTADO.clear()

    from webapp.config import salvar_config
    salvar_config(tmp_path / "config.json", {"Tecnologia": "gestor.ti@fucape.br"})

    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    client = TestClient(main.app)
    with caminho.open("rb") as arquivo:
        client.post("/upload", files={"arquivo": ("cartaoponto.xlsx", arquivo,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    monkeypatch.setenv("PAINEL_CEO_EMAIL", "ceo@fucape.br")
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "segredo")

    monkeypatch.setattr(main.deploy_netlify, "publicar", lambda pasta_base: "https://painel-fucape.netlify.app")
    monkeypatch.setattr(main.mailer_graph, "obter_token", lambda *a, **k: "token-123")

    destinatarios_chamados = []

    def fake_enviar(token, remetente, destinatarios, periodo, link):
        destinatarios_chamados.extend(destinatarios)
        assert link == "https://painel-fucape.netlify.app/2026-06/"
        return {destinatario: "ok" for destinatario in destinatarios}

    monkeypatch.setattr(main.mailer_graph, "enviar_notificacao", fake_enviar)

    resposta = client.post("/enviar")

    assert resposta.status_code == 200
    assert "ceo@fucape.br" in destinatarios_chamados
    assert "gestor.ti@fucape.br" in destinatarios_chamados
    assert "Todos os envios OK" in resposta.text


def test_post_enviar_com_falha_de_deploy_nao_envia_email(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(main, "CAMINHO_CONFIG", tmp_path / "config.json")
    main.ESTADO.clear()

    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    client = TestClient(main.app)
    with caminho.open("rb") as arquivo:
        client.post("/upload", files={"arquivo": ("cartaoponto.xlsx", arquivo,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    def falha_deploy(pasta_base):
        raise main.deploy_netlify.DeployError("not authenticated")

    monkeypatch.setattr(main.deploy_netlify, "publicar", falha_deploy)

    chamado = []
    monkeypatch.setattr(main.mailer_graph, "obter_token", lambda *a, **k: chamado.append(1))

    resposta = client.post("/enviar")

    assert resposta.status_code == 200
    assert "Falha ao publicar" in resposta.text
    assert chamado == []


def test_post_reenviar_sem_publicacao_redireciona_pro_index():
    main.ESTADO.clear()
    client = TestClient(main.app)

    resposta = client.post("/reenviar", follow_redirects=False)

    assert resposta.status_code == 303
    assert resposta.headers["location"] == "/"


def test_post_reenviar_manda_so_pra_quem_falhou(tmp_path, monkeypatch, workbook_path):
    monkeypatch.setattr(main, "PASTA_BASE", tmp_path / "painel_web")
    monkeypatch.setattr(main, "PASTA_UPLOADS", tmp_path / "uploads")
    monkeypatch.setattr(main, "CAMINHO_CONFIG", tmp_path / "config.json")
    main.ESTADO.clear()

    from webapp.config import salvar_config
    salvar_config(tmp_path / "config.json", {"Tecnologia": "gestor.ti@fucape.br"})

    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    client = TestClient(main.app)
    with caminho.open("rb") as arquivo:
        client.post("/upload", files={"arquivo": ("cartaoponto.xlsx", arquivo,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    monkeypatch.setenv("PAINEL_CEO_EMAIL", "ceo@fucape.br")
    monkeypatch.setenv("GRAPH_TENANT_ID", "tenant")
    monkeypatch.setenv("GRAPH_CLIENT_ID", "client")
    monkeypatch.setenv("GRAPH_CLIENT_SECRET", "segredo")
    monkeypatch.setattr(main.deploy_netlify, "publicar", lambda pasta_base: "https://painel-fucape.netlify.app")
    monkeypatch.setattr(main.mailer_graph, "obter_token", lambda *a, **k: "token-123")

    def enviar_com_uma_falha(token, remetente, destinatarios, periodo, link):
        return {
            destinatario: ("ok" if destinatario != "gestor.ti@fucape.br" else "erro: 400 endereço inválido")
            for destinatario in destinatarios
        }

    monkeypatch.setattr(main.mailer_graph, "enviar_notificacao", enviar_com_uma_falha)
    client.post("/enviar")
    assert main.ESTADO["ultima_publicacao"]["resultados"]["gestor.ti@fucape.br"].startswith("erro:")

    def reenviar_com_sucesso(token, remetente, destinatarios, periodo, link):
        assert destinatarios == ["gestor.ti@fucape.br"]
        return {"gestor.ti@fucape.br": "ok"}

    monkeypatch.setattr(main.mailer_graph, "enviar_notificacao", reenviar_com_sucesso)

    resposta = client.post("/reenviar")

    assert resposta.status_code == 200
    assert "Todos os envios OK" in resposta.text
    assert main.ESTADO["ultima_publicacao"]["resultados"]["gestor.ti@fucape.br"] == "ok"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_webapp_main.py -v`
Expected: FAIL — `/enviar` and `/reenviar` routes don't exist (404), `main.deploy_netlify`/`main.mailer_graph` not imported yet.

- [ ] **Step 3: Implement the route**

Add near the top of `webapp/main.py`, with the other imports:

```python
import os

from webapp import deploy_netlify, mailer_graph
```

Add at the end of `webapp/main.py`:

```python
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


@app.post("/enviar", response_class=HTMLResponse)
def enviar() -> HTMLResponse | RedirectResponse:
    resumo = ESTADO.get("ultimo")
    if not resumo:
        return RedirectResponse("/", status_code=303)

    mapa = config_mod.carregar_config(CAMINHO_CONFIG)
    destinatarios = [os.environ["PAINEL_CEO_EMAIL"]] + list(mapa.values())

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

    link = f"{url_site}/{resumo['periodo']}/"
    token = mailer_graph.obter_token(
        os.environ["GRAPH_TENANT_ID"], os.environ["GRAPH_CLIENT_ID"], os.environ["GRAPH_CLIENT_SECRET"],
    )
    remetente = os.environ.get("GRAPH_REMETENTE", "relatorios@fucape.br")
    resultados = mailer_graph.enviar_notificacao(token, remetente, destinatarios, resumo["periodo"], link)

    ESTADO["ultima_publicacao"] = {"link": link, "periodo": resumo["periodo"], "resultados": resultados}
    return _renderizar_resultado(link, resultados)


@app.post("/reenviar", response_class=HTMLResponse)
def reenviar() -> HTMLResponse | RedirectResponse:
    publicacao = ESTADO.get("ultima_publicacao")
    if not publicacao:
        return RedirectResponse("/", status_code=303)

    destinatarios_com_falha = [
        destinatario for destinatario, msg in publicacao["resultados"].items() if msg != "ok"
    ]
    token = mailer_graph.obter_token(
        os.environ["GRAPH_TENANT_ID"], os.environ["GRAPH_CLIENT_ID"], os.environ["GRAPH_CLIENT_SECRET"],
    )
    remetente = os.environ.get("GRAPH_REMETENTE", "relatorios@fucape.br")
    novos_resultados = mailer_graph.enviar_notificacao(
        token, remetente, destinatarios_com_falha, publicacao["periodo"], publicacao["link"],
    )

    publicacao["resultados"].update(novos_resultados)
    return _renderizar_resultado(publicacao["link"], publicacao["resultados"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_webapp_main.py -v`
Expected: PASS (12 passed)

- [ ] **Step 5: Run the full test suite**

Run: `pytest -v`
Expected: all tests pass, including the pre-existing `painel_horas`/`atualizar_painel` suite (untouched by this plan).

- [ ] **Step 6: Commit**

```bash
git add webapp/main.py tests/test_webapp_main.py
git commit -m "feat: wire send button to Netlify deploy and Graph API notification"
```

---

### Task 9: Local entry point and manual verification

**Files:**
- Create: `iniciar_painel_web.py`
- Create: `iniciar_painel_web.bat`
- Modify: `docs/superpowers/specs/2026-07-13-painel-web-graph-api-design.md` (append a "Verificação manual" note — no code change, just docs)

This task has no automated test — it needs a real Netlify CLI login and a real Entra ID app registration, which only exist in the company's actual environment (not the CI/dev machine building this plan). It ends with a documented manual checklist instead of a `pytest` step.

- [ ] **Step 1: Create the entry point script**

Create `iniciar_painel_web.py`:

```python
import webbrowser

import uvicorn

HOST = "127.0.0.1"
PORTA = 8000


def main() -> None:
    webbrowser.open(f"http://{HOST}:{PORTA}/")
    uvicorn.run("webapp.main:app", host=HOST, port=PORTA)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Create the Windows launcher**

Create `iniciar_painel_web.bat`:

```bat
@echo off
python iniciar_painel_web.py
pause
```

- [ ] **Step 3: Commit the entry point**

```bash
git add iniciar_painel_web.py iniciar_painel_web.bat
git commit -m "feat: add local entry point to launch the webapp prototype"
```

- [ ] **Step 4: Manual verification checklist (run once, by hand, before showing this to the responsável)**

Prerequisites to set up once, outside this repo:
1. Install the Netlify CLI (`npm install -g netlify-cli`) and run `netlify login` on the machine that will run this prototype; create a Netlify site once (`netlify sites:create`) and note its name.
2. Register an Entra ID app (Azure Portal → App registrations), grant it the **application** permission `Mail.Send` on Microsoft Graph with admin consent, and create a client secret. Ask the M365 admin to create the shared mailbox `relatorios@fucape.br` if it doesn't exist yet, and to grant the app permission to send as that mailbox (`Mail.Send` application permission covers this by default across the tenant unless scoped down — if IT restricts it, use an `applicationAccessPolicy` scoped to that mailbox instead of tenant-wide).
3. Set environment variables before running: `PAINEL_CEO_EMAIL`, `GRAPH_TENANT_ID`, `GRAPH_CLIENT_ID`, `GRAPH_CLIENT_SECRET` (and optionally `GRAPH_REMETENTE` if not using the `relatorios@fucape.br` default).

Manual verification steps:
1. Run `iniciar_painel_web.bat` (or `python iniciar_painel_web.py`) — confirm the browser opens to `http://127.0.0.1:8000/` showing the upload form.
2. Upload a real `cartaoponto.xlsx` — confirm it redirects to `/preview`, shows the correct counts, and the iframe renders the actual dashboard (ranking, department cards, working "mensal/semanal/diário" tabs on a person page).
3. Fill in at least one department's manager email in the config form, click "Salvar configuração" — confirm it redirects back to `/preview` with the value persisted (reload the page).
4. Click "Enviar", confirm the JS `confirm()` dialog, confirm the result page shows "Publicado em https://.../<periodo>/" and "Todos os envios OK".
5. Open the printed link from a phone on mobile data (not the company Wi-Fi) — confirm the dashboard loads and the person-page tabs still work (this is the SharePoint problem this design was chosen to avoid — verify it actually doesn't happen on Netlify).
6. Check that the CEO/test manager mailbox actually received the email with the correct link.
7. Re-run the whole flow with a different period's file — confirm the previous period's link (step 5) still resolves after this second deploy (this is the history-preservation guarantee from the spec).
