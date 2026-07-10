# Painel de Horas FUCAPE — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `atualizar_painel.py`, a double-click-friendly script that reads the Secullum hours-bank xlsx export and generates a self-contained dark-theme HTML dashboard (`painel/index.html` for the CEO) plus one scoped HTML page per department (`painel/deptos/*.html`) for the respective manager, matching the reference artifact's layout.

**Architecture:** Small Python package (`painel_horas/`) with pure, independently-testable modules — xlsx parsing, hour-string math, department slugging, and business-rule aggregation — feeding a single Jinja2 template rendered once per scope (general + each department). `atualizar_painel.py` at the repo root is the thin CLI entrypoint that wires it together, writes the files, and opens the result in a browser.

**Tech Stack:** Python 3.12, `openpyxl` (xlsx reading), `jinja2` (HTML templating), `pytest` (tests). No web server, no JS framework — vanilla JS for the one interactive control (ranking filter buttons).

**Spec source:** `docs/superpowers/specs/2026-07-10-painel-horas-fucape-design.md`

## Global Constraints

- Every generated HTML file must be self-contained (CSS + JS inline) — no external `<link>`/`<script src>` — so it works as a lone email attachment.
- The script must never crash the whole run on one malformed employee block; log a warning to console and fall back (`"Sem Departamento"`, `admissao=None`) instead.
- The script must never overwrite `painel/` if `extratos/` has no `.xlsx` — print an error and stop.
- Real data files (`*.xlsx`, `*.mhtml`, `*.pdf`, `painel/`) are already gitignored — never commit them, and tests must not depend on the real `ExtratoBancoHoras.xlsx` existing (build synthetic fixtures with `openpyxl` in `conftest.py`).
- Departments **Controladoria + Administrativo + Financeiro** merge into one page, label `"Centro de Serviços Compartilhados"`, slug `centro-servicos-compartilhados`. Comercial keeps its own page. (Originally specified as Controladoria+Comercial+Financeiro; corrected post-merge — see `CSC_ORIGENS` in painel_horas/calculos.py.)
- Slugs drop Portuguese connective words (`de`, `da`, `do`, `das`, `dos`, `e`) — verified against the spec's own file tree (`coordenacao-curso.html`, not `coordenacao-de-curso.html`; `gente-cultura.html`, not `gente-e-cultura.html`).
- "Config/isento" (não elegível) threshold: débito do período trabalhado ≥ 300h (18000 min) **and** crédito do período trabalhado ≤ 5% do débito — verified against the real xlsx, yields exactly the 9 flagged records the reference artifact describes. (Originally specified as an absolute ≤1h/60min crédito tolerance; corrected post-merge to a ratio after a real record — THIAGO SOUZA DOS SANTOS, 826 min crédito from real January punches vs 25580 min config-débito from May onward, a 3.2% ratio — was wrongly excluded by the absolute cutoff. See `TOLERANCIA_CREDITO_CONFIG_RATIO` in painel_horas/calculos.py.)
- Ranking bar scale: clamp at ±40h (2400 min); `pct = min(abs(minutos)/2400, 1) * 50` — verified formula reproduces the reference artifact's exact bar widths (e.g. `+38h10` → `47.7083%`).
- All money-shaped hour values use `format_horas`: sign (`+`/`−` U+2212), then `HhMM` (e.g. `+217h16`, `−3h11`).

---

## File Structure

```
secullum-painel-fucape/
├── atualizar_painel.bat
├── atualizar_painel.py            # CLI entrypoint (parses, generates, opens browser)
├── requirements.txt
├── painel_horas/
│   ├── __init__.py
│   ├── horas.py                   # parse_horas / format_horas
│   ├── slug.py                    # slugify (drops PT connectives)
│   ├── parser.py                  # Mes / Colaborador dataclasses + ler_colaboradores
│   ├── calculos.py                # business rules + montar_relatorio(...)
│   └── template.py                # render_pagina(contexto) -> str
├── templates/
│   └── painel.html.j2
├── extratos/
│   └── .gitkeep                   # user drops ExtratoBancoHoras.xlsx here
└── tests/
    ├── conftest.py                # synthetic xlsx workbook builder fixture
    ├── test_horas.py
    ├── test_slug.py
    ├── test_parser.py
    ├── test_calculos.py
    └── test_atualizar_painel.py   # end-to-end smoke test
```

---

### Task 1: Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `painel_horas/__init__.py`
- Create: `extratos/.gitkeep`
- Create: `atualizar_painel.bat`

**Interfaces:**
- Produces: installable dependency list, importable `painel_horas` package, the folder later tasks write into.

- [ ] **Step 1: Create `requirements.txt`**

```
openpyxl>=3.1
jinja2>=3.1
pytest>=8.0
```

- [ ] **Step 2: Create empty package marker**

`painel_horas/__init__.py`:
```python
```

- [ ] **Step 3: Create `extratos/.gitkeep`**

```
```

- [ ] **Step 4: Create `atualizar_painel.bat`**

```bat
@echo off
cd /d "%~dp0"
python atualizar_painel.py
pause
```

- [ ] **Step 5: Verify tooling installed**

Run: `pip install -r requirements.txt`
Expected: openpyxl, jinja2, pytest install without error (already installed in this environment, confirm no errors).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt painel_horas/__init__.py extratos/.gitkeep atualizar_painel.bat
git commit -m "chore: scaffold painel-horas project structure"
```

---

### Task 2: Hour-string math (`painel_horas/horas.py`)

**Files:**
- Create: `painel_horas/horas.py`
- Test: `tests/test_horas.py`

**Interfaces:**
- Produces: `parse_horas(valor) -> int` (signed minutes), `format_horas(minutos: int) -> str` — used by every later module.

- [ ] **Step 1: Write the failing test**

`tests/test_horas.py`:
```python
import datetime
from painel_horas.horas import parse_horas, format_horas


def test_parse_horas_timedelta_positivo():
    assert parse_horas(datetime.timedelta(hours=2, minutes=28)) == 148


def test_parse_horas_timedelta_zero():
    assert parse_horas(datetime.timedelta(0)) == 0


def test_parse_horas_none():
    assert parse_horas(None) == 0


def test_parse_horas_string_negativa():
    assert parse_horas("-03:11") == -191


def test_parse_horas_string_negativa_grande():
    # débito de config isento pode passar de 24h: -360:00
    assert parse_horas("-360:00") == -21600


def test_format_horas_positivo():
    assert format_horas(148) == "+2h28"


def test_format_horas_negativo():
    assert format_horas(-191) == "−3h11"


def test_format_horas_zero():
    assert format_horas(0) == "+0h00"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_horas.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'painel_horas.horas'`

- [ ] **Step 3: Write minimal implementation**

`painel_horas/horas.py`:
```python
import datetime


def parse_horas(valor) -> int:
    """Normaliza um valor de hora do extrato Secullum para minutos assinados."""
    if valor is None:
        return 0
    if isinstance(valor, datetime.timedelta):
        return int(valor.total_seconds() // 60)
    if isinstance(valor, str):
        texto = valor.strip()
        negativo = texto.startswith("-")
        texto = texto.lstrip("-")
        horas_str, minutos_str = texto.split(":")
        total = int(horas_str) * 60 + int(minutos_str)
        return -total if negativo else total
    raise TypeError(f"valor de hora inesperado: {valor!r}")


def format_horas(minutos: int) -> str:
    """Formata minutos assinados como '+217h16' / '−3h11'."""
    sinal = "+" if minutos >= 0 else "−"
    minutos_abs = abs(minutos)
    horas, resto = divmod(minutos_abs, 60)
    return f"{sinal}{horas}h{resto:02d}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_horas.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add painel_horas/horas.py tests/test_horas.py
git commit -m "feat: add hour-string parsing and formatting helpers"
```

---

### Task 3: Department slugging (`painel_horas/slug.py`)

**Files:**
- Create: `painel_horas/slug.py`
- Test: `tests/test_slug.py`

**Interfaces:**
- Produces: `slugify(nome: str) -> str`

- [ ] **Step 1: Write the failing test**

`tests/test_slug.py`:
```python
from painel_horas.slug import slugify


def test_slugify_nomes_simples():
    assert slugify("Hub Fucape") == "hub-fucape"
    assert slugify("Tecnologia") == "tecnologia"
    assert slugify("Biblioteca") == "biblioteca"
    assert slugify("Diretoria") == "diretoria"
    assert slugify("Administrativo") == "administrativo"
    assert slugify("Atendimento") == "atendimento"
    assert slugify("Marketing") == "marketing"


def test_slugify_remove_acentos():
    assert slugify("Comunicação") == "comunicacao"
    assert slugify("Secretaria Academica") == "secretaria-academica"


def test_slugify_remove_conectivos():
    assert slugify("Centro de Serviços Compartilhados") == "centro-servicos-compartilhados"
    assert slugify("Secretaria de Pesquisa") == "secretaria-pesquisa"
    assert slugify("Coordenação de Curso") == "coordenacao-curso"
    assert slugify("Gente e Cultura") == "gente-cultura"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_slug.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'painel_horas.slug'`

- [ ] **Step 3: Write minimal implementation**

`painel_horas/slug.py`:
```python
import unicodedata

CONECTIVOS = {"de", "da", "do", "das", "dos", "e"}


def slugify(nome: str) -> str:
    """Converte um nome de departamento em slug de arquivo, removendo
    acentos e conectivos em português (de/da/do/das/dos/e)."""
    normalizado = unicodedata.normalize("NFKD", nome)
    sem_acento = "".join(c for c in normalizado if not unicodedata.combining(c))
    palavras = [p for p in sem_acento.lower().split() if p not in CONECTIVOS]
    return "-".join(palavras)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_slug.py -v`
Expected: PASS (9 assertions across 3 tests)

- [ ] **Step 5: Commit**

```bash
git add painel_horas/slug.py tests/test_slug.py
git commit -m "feat: add department name slugifier"
```

---

### Task 4: xlsx parsing (`painel_horas/parser.py`)

**Files:**
- Create: `painel_horas/parser.py`
- Create: `tests/conftest.py`
- Test: `tests/test_parser.py`

**Interfaces:**
- Consumes: nothing internal (only `openpyxl`).
- Produces: `Mes` dataclass (`inicio: date, fim: date, total_min: int, credito_min: int, debito_min: int, ajuste_min: int`), `Colaborador` dataclass (`nome: str, funcao: str, admissao: date | None, departamento: str, meses: list[Mes], total_bruto_min: int, credito_total_min: int, debito_total_min: int, ajuste_total_min: int`), `ler_colaboradores(caminho_xlsx) -> list[Colaborador]` — consumed by `calculos.py` and `atualizar_painel.py`.

- [ ] **Step 1: Write the synthetic-workbook fixture**

`tests/conftest.py`:

Note: every cell value passed in `meses` or `total` must be a `datetime.timedelta`
or a `"-HH:MM"`-style string — exactly what `parse_horas` (Task 2) accepts. This
mirrors the real xlsx, where Excel never stores a negative `timedelta` (it stores
a string instead) and never stores a plain `int`/`float` for these columns.

```python
import openpyxl
import pytest


@pytest.fixture
def workbook_path(tmp_path):
    def _construir(blocos):
        """`blocos` é uma lista de dicts com chaves:
        nome, funcao, admissao, departamento, meses, total (tupla final TOTAL row).
        Os valores de hora em `meses` e `total` devem ser datetime.timedelta ou
        string "-HH:MM" — nunca int/float cru (o xlsx real nunca guarda isso)."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        linha = 1
        for bloco in blocos:
            ws.cell(row=linha, column=1, value="EXTRATO DO BANCO DE HORAS")
            ws.cell(row=linha + 1, column=1, value="Período: 01/01/2026 até 09/07/2026.")
            ws.cell(row=linha + 3, column=1, value="EMPRESA: FUCAPE PESQUISA E ENSINO SA")
            ws.cell(row=linha + 4, column=1, value=f"NOME: {bloco['nome']}")
            ws.cell(row=linha + 5, column=1, value=f"FUNÇÃO: {bloco['funcao']}")
            ws.cell(
                row=linha + 5, column=3,
                value=f"ADMISSÃO: {bloco['admissao']}" if bloco["admissao"] else "ADMISSÃO: ",
            )
            ws.cell(
                row=linha + 6, column=1,
                value=f"DEPARTAMENTO: {bloco['departamento']}" if bloco["departamento"] else "DEPARTAMENTO: ",
            )
            ws.cell(row=linha + 7, column=1, value="OBSERVAÇÃO: ")
            ws.cell(row=linha + 9, column=1, value="PERÍODO")
            ws.cell(row=linha + 9, column=2, value="TOTAL")
            ws.cell(row=linha + 9, column=3, value="CRÉDITO")
            ws.cell(row=linha + 9, column=4, value="DÉBITO")
            ws.cell(row=linha + 9, column=5, value="AJUSTE")
            r = linha + 10
            for periodo_str, total, credito, debito, ajuste in bloco["meses"]:
                ws.cell(row=r, column=1, value=periodo_str)
                ws.cell(row=r, column=2, value=total)
                ws.cell(row=r, column=3, value=credito)
                ws.cell(row=r, column=4, value=debito)
                ws.cell(row=r, column=5, value=ajuste)
                r += 1
            total_total, total_credito, total_debito, total_ajuste = bloco["total"]
            ws.cell(row=r, column=1, value="TOTAL")
            ws.cell(row=r, column=2, value=total_total)
            ws.cell(row=r, column=3, value=total_credito)
            ws.cell(row=r, column=4, value=total_debito)
            ws.cell(row=r, column=5, value=total_ajuste)
            linha = r + 4
        caminho = tmp_path / "extrato_teste.xlsx"
        wb.save(caminho)
        return caminho
    return _construir
```

- [ ] **Step 2: Write the failing test**

`tests/test_parser.py`:
```python
import datetime
from painel_horas.parser import ler_colaboradores


def test_ler_colaboradores_bloco_completo(workbook_path):
    caminho = workbook_path([
        {
            "nome": "ANA CARLA CRISTOVAO DA SILVA",
            "funcao": "ASSISTENTE DE COORDENAÇÃO",
            "admissao": "13/05/2026",
            "departamento": "COORDENAÇÃO DE CURSO",
            "meses": [
                ("01/05/2026 até 31/05/2026", datetime.timedelta(hours=2, minutes=28),
                 datetime.timedelta(hours=17, minutes=16), datetime.timedelta(hours=14, minutes=48),
                 datetime.timedelta(0)),
                ("01/06/2026 até 30/06/2026", "-03:11", "05:00", "08:11", "00:00"),
            ],
            "total": ("-00:42", datetime.timedelta(hours=22, minutes=17), datetime.timedelta(hours=22, minutes=59), datetime.timedelta(0)),
        },
    ])

    colaboradores = ler_colaboradores(caminho)

    assert len(colaboradores) == 1
    c = colaboradores[0]
    assert c.nome == "ANA CARLA CRISTOVAO DA SILVA"
    assert c.funcao == "ASSISTENTE DE COORDENAÇÃO"
    assert c.admissao == datetime.date(2026, 5, 13)
    assert c.departamento == "COORDENAÇÃO DE CURSO"
    assert len(c.meses) == 2
    assert c.meses[0].inicio == datetime.date(2026, 5, 1)
    assert c.meses[0].fim == datetime.date(2026, 5, 31)
    assert c.meses[0].total_min == 148
    assert c.meses[1].total_min == -191
    assert c.total_bruto_min == -42
    assert c.credito_total_min == 1337
    assert c.debito_total_min == 1379


def test_ler_colaboradores_bloco_incompleto_usa_fallback(workbook_path, capsys):
    caminho = workbook_path([
        {
            "nome": "FULANO SEM DADOS",
            "funcao": "ESTAGIARIO",
            "admissao": None,
            "departamento": None,
            "meses": [
                ("01/06/2026 até 30/06/2026", datetime.timedelta(0), datetime.timedelta(0),
                 datetime.timedelta(0), datetime.timedelta(0)),
            ],
            "total": (datetime.timedelta(0), datetime.timedelta(0), datetime.timedelta(0), datetime.timedelta(0)),
        },
    ])

    colaboradores = ler_colaboradores(caminho)

    assert len(colaboradores) == 1
    c = colaboradores[0]
    assert c.admissao is None
    assert c.departamento == "Sem Departamento"
    saida = capsys.readouterr()
    assert "FULANO SEM DADOS" in saida.out


def test_ler_colaboradores_multiplos_blocos(workbook_path):
    caminho = workbook_path([
        {
            "nome": "PESSOA UM", "funcao": "CARGO A", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "meses": [("01/06/2026 até 30/06/2026", datetime.timedelta(hours=1),
                       datetime.timedelta(hours=1), datetime.timedelta(0), datetime.timedelta(0))],
            "total": (datetime.timedelta(hours=1), datetime.timedelta(hours=1), datetime.timedelta(0), datetime.timedelta(0)),
        },
        {
            "nome": "PESSOA DOIS", "funcao": "CARGO B", "admissao": "01/02/2020",
            "departamento": "BIBLIOTECA",
            "meses": [("01/06/2026 até 30/06/2026", datetime.timedelta(hours=-1),
                       datetime.timedelta(0), datetime.timedelta(hours=1), datetime.timedelta(0))],
            "total": ("-01:00", datetime.timedelta(0), datetime.timedelta(hours=1), datetime.timedelta(0)),
        },
    ])

    colaboradores = ler_colaboradores(caminho)

    assert [c.nome for c in colaboradores] == ["PESSOA UM", "PESSOA DOIS"]
    assert colaboradores[0].departamento == "TECNOLOGIA"
    assert colaboradores[1].departamento == "BIBLIOTECA"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_parser.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'painel_horas.parser'`

- [ ] **Step 4: Write minimal implementation**

`painel_horas/parser.py`:
```python
from dataclasses import dataclass, field
from datetime import date

import openpyxl

from painel_horas.horas import parse_horas


@dataclass
class Mes:
    inicio: date
    fim: date
    total_min: int
    credito_min: int
    debito_min: int
    ajuste_min: int


@dataclass
class Colaborador:
    nome: str
    funcao: str
    admissao: date | None
    departamento: str
    meses: list[Mes] = field(default_factory=list)
    total_bruto_min: int = 0
    credito_total_min: int = 0
    debito_total_min: int = 0
    ajuste_total_min: int = 0


def _parse_data(texto: str) -> date:
    dia, mes, ano = texto.strip().split("/")
    return date(int(ano), int(mes), int(dia))


def ler_colaboradores(caminho_xlsx) -> list[Colaborador]:
    wb = openpyxl.load_workbook(caminho_xlsx, data_only=True)
    ws = wb["Sheet1"] if "Sheet1" in wb.sheetnames else wb.worksheets[0]
    max_row = ws.max_row

    def val(linha, coluna):
        return ws.cell(row=linha, column=coluna).value

    colaboradores: list[Colaborador] = []
    r = 1
    while r <= max_row:
        v = val(r, 1)
        if not (isinstance(v, str) and v.startswith("NOME:")):
            r += 1
            continue

        nome = v.split(":", 1)[1].strip()
        funcao = ""
        admissao: date | None = None
        departamento = "Sem Departamento"
        incompleto = False

        limite = min(max_row, r + 6)
        j = r + 1
        while j <= limite:
            vj1 = val(j, 1)
            if isinstance(vj1, str) and vj1.startswith("FUN"):
                funcao = vj1.split(":", 1)[1].strip()
                vj3 = val(j, 3)
                data_str = ""
                if isinstance(vj3, str) and "ADMISS" in vj3.upper():
                    data_str = vj3.split(":", 1)[1].strip()
                if data_str:
                    admissao = _parse_data(data_str)
                else:
                    incompleto = True
            elif isinstance(vj1, str) and vj1.startswith("DEPARTAMENTO:"):
                dep = vj1.split(":", 1)[1].strip()
                if dep:
                    departamento = dep
                else:
                    incompleto = True
            elif vj1 == "PERÍODO":
                break
            j += 1

        if incompleto:
            print(f"[aviso] colaborador '{nome}' com admissão/departamento incompleto — usando fallback")

        header_row = j
        meses: list[Mes] = []
        k = header_row + 1
        total_bruto = credito_total = debito_total = ajuste_total = 0
        while k <= max_row:
            vk1 = val(k, 1)
            if vk1 == "TOTAL":
                total_bruto = parse_horas(val(k, 2))
                credito_total = parse_horas(val(k, 3))
                debito_total = parse_horas(val(k, 4))
                ajuste_total = parse_horas(val(k, 5))
                k += 1
                break
            if isinstance(vk1, str) and " até " in vk1:
                inicio_str, fim_str = vk1.split(" até ")
                meses.append(Mes(
                    inicio=_parse_data(inicio_str),
                    fim=_parse_data(fim_str),
                    total_min=parse_horas(val(k, 2)),
                    credito_min=parse_horas(val(k, 3)),
                    debito_min=parse_horas(val(k, 4)),
                    ajuste_min=parse_horas(val(k, 5)),
                ))
            k += 1

        colaboradores.append(Colaborador(
            nome=nome, funcao=funcao, admissao=admissao, departamento=departamento,
            meses=meses, total_bruto_min=total_bruto, credito_total_min=credito_total,
            debito_total_min=debito_total, ajuste_total_min=ajuste_total,
        ))
        r = k

    return colaboradores
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_parser.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add painel_horas/parser.py tests/conftest.py tests/test_parser.py
git commit -m "feat: parse Secullum hours-bank xlsx into Colaborador records"
```

---

### Task 5: Business rules (`painel_horas/calculos.py`)

**Files:**
- Create: `painel_horas/calculos.py`
- Test: `tests/test_calculos.py`

**Interfaces:**
- Consumes: `Colaborador`/`Mes` from `painel_horas.parser`, `format_horas` from `painel_horas.horas`, `slugify` from `painel_horas.slug`.
- Produces: `dept_label(departamento: str) -> str`, `saldo_trabalhado_min(colab) -> int`, `is_config(colab) -> bool`, `montar_relatorio(colaboradores: list[Colaborador], escopo: str) -> dict` — consumed by `atualizar_painel.py` and `template.py` (via the context dict's `"r"` key). `escopo` is one of `"geral"`, `"depto"`, `"csc"`.

- [ ] **Step 1: Write the failing test**

`tests/test_calculos.py`:
```python
import datetime
from painel_horas.parser import Colaborador, Mes
from painel_horas.calculos import (
    dept_label, saldo_trabalhado_min, is_config, montar_relatorio,
    LIMITE_DEBITO_CONFIG_MIN, TOLERANCIA_CREDITO_CONFIG_MIN,
)


def _colab(nome, departamento, admissao, meses_totais, total_bruto=None, credito_total=None, debito_total=None):
    """meses_totais: lista de (inicio, fim, total, credito, debito)"""
    meses = [
        Mes(inicio=i, fim=f, total_min=t, credito_min=c, debito_min=d, ajuste_min=0)
        for (i, f, t, c, d) in meses_totais
    ]
    return Colaborador(
        nome=nome, funcao="Cargo Teste", admissao=admissao, departamento=departamento,
        meses=meses,
        total_bruto_min=total_bruto if total_bruto is not None else sum(m.total_min for m in meses),
        credito_total_min=credito_total if credito_total is not None else sum(m.credito_min for m in meses),
        debito_total_min=debito_total if debito_total is not None else sum(m.debito_min for m in meses),
    )


def test_dept_label_agrupa_csc():
    assert dept_label("CONTROLADORIA") == "Centro de Serviços Compartilhados"
    assert dept_label("Comercial") == "Centro de Serviços Compartilhados"
    assert dept_label("FINANCEIRO") == "Centro de Serviços Compartilhados"


def test_dept_label_mantem_outros():
    assert dept_label("TECNOLOGIA") == "Tecnologia"
    assert dept_label("HUB FUCAPE") == "Hub Fucape"


def test_saldo_trabalhado_filtra_meses_antes_da_admissao():
    c = _colab(
        "Recem Admitido", "TECNOLOGIA", admissao=datetime.date(2026, 5, 13),
        meses_totais=[
            (datetime.date(2026, 4, 1), datetime.date(2026, 4, 30), -18000, 0, 18000),  # antes da admissão
            (datetime.date(2026, 5, 1), datetime.date(2026, 5, 31), 363, 363, 0),        # 6h03 depois da admissão
        ],
    )
    assert saldo_trabalhado_min(c) == 363


def test_saldo_trabalhado_sem_admissao_usa_total():
    c = _colab(
        "Sem Data", "TECNOLOGIA", admissao=None,
        meses_totais=[(datetime.date(2026, 5, 1), datetime.date(2026, 5, 31), 100, 100, 0)],
    )
    assert saldo_trabalhado_min(c) == 100


def test_is_config_detecta_debito_padrao_sem_credito():
    c = _colab(
        "Isento", "DIRETORIA", admissao=datetime.date(2020, 1, 1),
        meses_totais=[(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), -21600, 0, 21600)],
    )
    assert is_config(c) is True


def test_is_config_falso_quando_ha_credito_real():
    c = _colab(
        "Com Ponto", "TECNOLOGIA", admissao=datetime.date(2020, 1, 1),
        meses_totais=[(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), 100, 200, 100)],
    )
    assert is_config(c) is False


def test_is_config_falso_quando_debito_abaixo_do_limite():
    c = _colab(
        "Debito Pequeno", "TECNOLOGIA", admissao=datetime.date(2020, 1, 1),
        meses_totais=[(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), -100, 0, 100)],
    )
    assert is_config(c) is False


def test_limites_config_batem_com_o_spec():
    assert LIMITE_DEBITO_CONFIG_MIN == 300 * 60
    assert TOLERANCIA_CREDITO_CONFIG_MIN == 60


def test_montar_relatorio_geral_gera_kpis_gauge_ranking_e_deptos():
    positivo = _colab(
        "Credor Grande", "HUB FUCAPE", admissao=datetime.date(2020, 1, 1),
        meses_totais=[(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), 6775, 6775, 0)],
    )  # +112h55
    negativo = _colab(
        "Devedor", "TECNOLOGIA", admissao=datetime.date(2020, 1, 1),
        meses_totais=[(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), -1181, 0, 1181)],
    )  # -19h41
    isento = _colab(
        "Config", "DIRETORIA", admissao=datetime.date(2020, 1, 1),
        meses_totais=[(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), -21600, 0, 21600)],
    )

    r = montar_relatorio([positivo, negativo, isento], escopo="geral")

    assert r["contadores"] == {"total": 3, "elegiveis": 2, "nao_elegiveis": 1}
    assert r["ranking"][0]["nome"] == "Credor Grande"
    assert r["ranking"][0]["classe"] == "p"
    assert r["ranking"][0]["valor_fmt"] == "+112h55"
    # +112h55 (6775 min) > escala de 2400 min -> barra travada no teto (50%)
    assert r["ranking"][0]["pct"] == 50.0
    assert r["nota_ranking"] is not None and "Credor" in r["nota_ranking"]
    assert r["ranking"][1]["nome"] == "Devedor"
    assert r["ranking"][1]["classe"] == "n"

    assert r["gauge"]["qtd_passivo"] == 1
    assert r["gauge"]["qtd_receber"] == 1
    assert r["gauge"]["pos_fmt"] == "+112h55"
    assert r["gauge"]["neg_fmt"] == "−19h41"
    assert round(r["gauge"]["neg_pct"] + r["gauge"]["pos_pct"], 4) == 100.0

    assert r["kpis"]["nao_elegiveis"]["valor"] == 1
    assert r["kpis"]["concentracao"]["valor_fmt"] == "+112h55"
    assert r["kpis"]["concentracao"]["pct_fmt"] == "100%"

    assert r["alerta"] is not None and "1 registro" in r["alerta"]

    # "Diretoria" tem só o colaborador "Config" (não elegível), então some do grid
    # de departamentos — a seção 02 só soma saldo de gente com ponto ativo.
    nomes_deptos = {d["nome"] for d in r["deptos"]}
    assert nomes_deptos == {"Hub Fucape", "Tecnologia"}

    assert r["nao_elegiveis_lista"][0]["nome"] == "Config"
    assert r["nao_elegiveis_lista"][0]["valor_fmt"] == "−360h00"


def test_montar_relatorio_depto_sem_deptos_e_subtitulo_admissao():
    recente = _colab(
        "Recem Chegado", "COORDENAÇÃO DE CURSO", admissao=datetime.date(2026, 5, 13),
        meses_totais=[
            (datetime.date(2026, 4, 1), datetime.date(2026, 4, 30), -18000, 0, 18000),
            (datetime.date(2026, 5, 1), datetime.date(2026, 5, 31), 363, 363, 0),
        ],
        total_bruto=-17637,
    )
    r = montar_relatorio([recente], escopo="depto")
    assert r["deptos"] is None
    assert "admitido 13/05/2026" in r["ranking"][0]["subtitulo"]
    assert "desde admissão: +6h03" in r["ranking"][0]["subtitulo"]


def test_montar_relatorio_csc_mostra_time_original():
    membro = _colab(
        "Pessoa CSC", "Controladoria", admissao=datetime.date(2020, 1, 1),
        meses_totais=[(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), 100, 100, 0)],
    )
    r = montar_relatorio([membro], escopo="csc")
    assert r["ranking"][0]["subtitulo"] == "Controladoria"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_calculos.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'painel_horas.calculos'`

- [ ] **Step 3: Write minimal implementation**

`painel_horas/calculos.py`:
```python
from painel_horas.horas import format_horas
from painel_horas.slug import slugify

LIMITE_DEBITO_CONFIG_MIN = 300 * 60
TOLERANCIA_CREDITO_CONFIG_MIN = 60
ESCALA_RANKING_MAX_MIN = 40 * 60

CSC_ORIGENS = {"CONTROLADORIA", "COMERCIAL", "FINANCEIRO"}
CSC_LABEL = "Centro de Serviços Compartilhados"


def dept_label(departamento: str) -> str:
    if departamento.strip().upper() in CSC_ORIGENS:
        return CSC_LABEL
    return departamento.strip().title()


def _meses_periodo_trabalhado(colab):
    if colab.admissao is None:
        return colab.meses
    limite = (colab.admissao.year, colab.admissao.month)
    return [m for m in colab.meses if (m.inicio.year, m.inicio.month) >= limite]


def saldo_trabalhado_min(colab) -> int:
    meses = _meses_periodo_trabalhado(colab)
    if not meses:
        return colab.total_bruto_min
    return sum(m.total_min for m in meses)


def _credito_trabalhado_min(colab) -> int:
    meses = _meses_periodo_trabalhado(colab)
    if not meses:
        return colab.credito_total_min
    return sum(m.credito_min for m in meses)


def _debito_trabalhado_min(colab) -> int:
    meses = _meses_periodo_trabalhado(colab)
    if not meses:
        return colab.debito_total_min
    return sum(m.debito_min for m in meses)


def is_config(colab) -> bool:
    return (
        abs(_debito_trabalhado_min(colab)) >= LIMITE_DEBITO_CONFIG_MIN
        and abs(_credito_trabalhado_min(colab)) <= TOLERANCIA_CREDITO_CONFIG_MIN
    )


def _pct_ranking(minutos: int) -> float:
    return min(abs(minutos) / ESCALA_RANKING_MAX_MIN, 1.0) * 50


def _tooltip(colab) -> str:
    if colab.admissao is None:
        return f"{colab.funcao} · sem data de admissão"
    return f"{colab.funcao} · admitido {colab.admissao.strftime('%d/%m/%Y')}"


def _subtitulo(colab, escopo: str) -> str:
    if escopo == "geral":
        return dept_label(colab.departamento)
    if escopo == "csc":
        return colab.departamento.strip().title()
    if colab.admissao is None:
        return ""
    base = f"admitido {colab.admissao.strftime('%d/%m/%Y')}"
    trabalhado = saldo_trabalhado_min(colab)
    if trabalhado != colab.total_bruto_min:
        base += f" · desde admissão: {format_horas(trabalhado)}"
    return base


def montar_relatorio(colaboradores: list, escopo: str = "geral") -> dict:
    elegiveis = [c for c in colaboradores if not is_config(c)]
    nao_elegiveis = [c for c in colaboradores if is_config(c)]

    ranking_ordenado = sorted(elegiveis, key=lambda c: -c.total_bruto_min)
    passivo_lista = [c for c in elegiveis if c.total_bruto_min > 0]
    receber_lista = [c for c in elegiveis if c.total_bruto_min < 0]
    passivo_sum = sum(c.total_bruto_min for c in passivo_lista)
    receber_sum = sum(-c.total_bruto_min for c in receber_lista)
    total_abs = passivo_sum + receber_sum
    saldo_liquido_min = passivo_sum - receber_sum

    ranking = []
    maior_clamp = None
    for c in ranking_ordenado:
        if abs(c.total_bruto_min) >= ESCALA_RANKING_MAX_MIN:
            if maior_clamp is None or abs(c.total_bruto_min) > abs(maior_clamp.total_bruto_min):
                maior_clamp = c
        ranking.append({
            "nome": c.nome,
            "subtitulo": _subtitulo(c, escopo),
            "tooltip": _tooltip(c),
            "classe": "p" if c.total_bruto_min >= 0 else "n",
            "pct": _pct_ranking(c.total_bruto_min),
            "valor_fmt": format_horas(c.total_bruto_min),
        })

    nota_ranking = None
    if maior_clamp is not None:
        nota_ranking = (
            f"*{maior_clamp.nome.split()[0]} ({format_horas(maior_clamp.total_bruto_min)}) "
            "extrapola a escala; barra travada no teto para não achatar os demais."
        )

    if total_abs > 0:
        neg_pct = receber_sum / total_abs * 100
        pos_pct = passivo_sum / total_abs * 100
    else:
        neg_pct = pos_pct = 0.0

    nota_hero = (
        "A empresa deve mais horas do que tem a receber. Passivo trabalhista latente."
        if saldo_liquido_min >= 0 else
        "A empresa tem mais horas a receber do que deve. Situação favorável de banco de horas."
    )

    gauge = {
        "neg_pct": neg_pct,
        "pos_pct": pos_pct,
        "neg_fmt": format_horas(-receber_sum),
        "pos_fmt": format_horas(passivo_sum),
        "qtd_receber": len(receber_lista),
        "qtd_passivo": len(passivo_lista),
        "saldo_liquido_min": saldo_liquido_min,
        "saldo_liquido_fmt": format_horas(saldo_liquido_min),
        "nota_hero": nota_hero,
    }

    media_passivo = round(passivo_sum / len(passivo_lista)) if passivo_lista else 0
    media_receber = round(receber_sum / len(receber_lista)) if receber_lista else 0
    kpis = {
        "passivo": {
            "valor_fmt": format_horas(passivo_sum),
            "sub": f"{len(passivo_lista)} pessoa{'s' if len(passivo_lista) != 1 else ''} · média {format_horas(media_passivo)}",
        },
        "receber": {
            "valor_fmt": format_horas(-receber_sum),
            "sub": f"{len(receber_lista)} pessoa{'s' if len(receber_lista) != 1 else ''} · média {format_horas(-media_receber)}",
        },
        "nao_elegiveis": {
            "valor": len(nao_elegiveis),
            "sub": "Débito padrão configurado · não indica ausência real",
        },
    }
    if passivo_lista:
        topo = max(passivo_lista, key=lambda c: c.total_bruto_min)
        pct_concentracao = (topo.total_bruto_min / passivo_sum * 100) if passivo_sum else 0.0
        kpis["concentracao"] = {
            "valor_fmt": format_horas(topo.total_bruto_min),
            "pct_fmt": f"{pct_concentracao:.0f}%",
            "sub": f"{topo.nome.split()[0]} · {dept_label(topo.departamento)} · maior saldo individual",
        }
    else:
        kpis["concentracao"] = {"valor_fmt": format_horas(0), "pct_fmt": "0%", "sub": "sem concentração relevante"}

    alerta = None
    n_nao = len(nao_elegiveis)
    if n_nao:
        plural = n_nao != 1
        alerta = (
            f"{n_nao} registro{'s' if plural else ''} marca{'m' if plural else ''} débito padrão automático "
            "(isenção de ponto ou jornada mal configurada), sem crédito real correspondente. "
            "Foram isolados na seção 03 para não contaminar o ranking."
        )

    deptos = None
    if escopo == "geral":
        grupos: dict[str, list] = {}
        for c in elegiveis:
            grupos.setdefault(dept_label(c.departamento), []).append(c)
        deptos_lista = []
        for label, membros in grupos.items():
            soma = sum(m.total_bruto_min for m in membros)
            deptos_lista.append({
                "nome": label,
                "slug": slugify(label),
                "pessoas": len(membros),
                "media_fmt": format_horas(round(soma / len(membros))),
                "total_min": soma,
                "valor_fmt": format_horas(soma),
            })
        deptos_lista.sort(key=lambda d: -d["total_min"])
        max_abs = max((abs(d["total_min"]) for d in deptos_lista), default=1) or 1
        for d in deptos_lista:
            d["mini_pct"] = abs(d["total_min"]) / max_abs * 100
        deptos = deptos_lista

    nao_elegiveis_lista = [
        {
            "nome": c.nome,
            "funcao": c.funcao,
            "departamento": dept_label(c.departamento),
            "valor_fmt": format_horas(c.total_bruto_min),
        }
        for c in sorted(nao_elegiveis, key=lambda c: c.nome)
    ]

    return {
        "contadores": {
            "total": len(colaboradores),
            "elegiveis": len(elegiveis),
            "nao_elegiveis": len(nao_elegiveis),
        },
        "ranking": ranking,
        "nota_ranking": nota_ranking,
        "gauge": gauge,
        "kpis": kpis,
        "alerta": alerta,
        "deptos": deptos,
        "nao_elegiveis_lista": nao_elegiveis_lista,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_calculos.py -v`
Expected: PASS (11 tests)

- [ ] **Step 5: Commit**

```bash
git add painel_horas/calculos.py tests/test_calculos.py
git commit -m "feat: add business-rule aggregation (KPIs, gauge, ranking, deptos)"
```

---

### Task 6: Template rendering (`painel_horas/template.py` + `templates/painel.html.j2`)

**Files:**
- Create: `templates/painel.html.j2`
- Create: `painel_horas/template.py`
- Test: `tests/test_template.py`

**Interfaces:**
- Consumes: a context dict `{"escopo_titulo": str, "periodo_texto": str, "data_emissao": str, "mostrar_deptos": bool, "r": <output of montar_relatorio>}`.
- Produces: `render_pagina(contexto: dict) -> str` — consumed by `atualizar_painel.py`.

- [ ] **Step 1: Create the Jinja2 template**

`templates/painel.html.j2`:
```jinja2
<!DOCTYPE html><html lang="pt-BR"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Banco de Horas · {{ escopo_titulo }} · Fucape</title>
<style>
:root{--bg:#0b0f14;--panel:#121821;--panel2:#0e141c;--line:#1f2933;--ink:#e8edf2;--mut:#8a97a6;--pos:#3ddc84;--neg:#ff5c5c;--amber:#ffb020;--blue:#4da3ff}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:960px;margin:0 auto;padding:32px 24px 64px}
header{display:flex;justify-content:space-between;align-items:flex-start;gap:16px;border-bottom:1px solid var(--line);padding-bottom:20px;margin-bottom:24px}
.eyebrow{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);margin-bottom:6px}
h1{margin:0;font-size:24px;font-weight:800}
h1 span{color:var(--mut);font-weight:600}
.meta{font-size:12px;color:var(--mut);text-align:right}
.meta b{color:var(--ink)}
.hero{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:24px;margin-bottom:20px}
.hero-top{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:6px}
.hero-label{font-size:12px;text-transform:uppercase;letter-spacing:.05em;color:var(--mut)}
.hero-note{font-size:11.5px;color:var(--mut)}
.gauge{position:relative;display:flex;height:28px;border-radius:6px;overflow:hidden;margin-top:16px;background:var(--panel2)}
.seg{display:flex;align-items:center;font-size:12px;font-weight:700}
.seg.neg{background:var(--neg);color:#2a0b0b;justify-content:flex-end;padding-right:8px}
.seg.pos{background:var(--pos);color:#08110c;justify-content:flex-start;padding-left:8px}
.divider{position:absolute;top:0;bottom:0;width:2px;background:var(--ink);opacity:.6}
.gauge-legend{display:flex;justify-content:space-between;font-size:11.5px;color:var(--mut);margin-top:8px}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}
.kpi{background:var(--panel);border:1px solid var(--line);border-left:3px solid var(--mut);border-radius:8px;padding:14px}
.kpi.p{border-left-color:var(--pos)}
.kpi.n{border-left-color:var(--neg)}
.kpi.a{border-left-color:var(--amber)}
.kpi.b{border-left-color:var(--blue)}
.k-val{font-size:20px;font-weight:800}
.k-lab{font-size:11.5px;color:var(--mut);margin-top:4px}
.k-sub{font-size:11px;color:var(--mut);margin-top:6px;opacity:.85}
.tpos{color:var(--pos)}
.tneg{color:var(--neg)}
.alert{background:#2a2410;border:1px solid #4d3f12;color:#e8dcae;border-radius:8px;padding:14px 16px;font-size:12.5px;margin-bottom:20px}
section{margin-bottom:28px}
.s-head{display:flex;align-items:baseline;gap:10px;margin-bottom:4px}
.idx{font-size:11px;color:var(--mut);font-weight:700}
h2{margin:0;font-size:16px}
.s-sub{font-size:12px;color:var(--mut);margin-bottom:12px}
.controls{display:flex;align-items:center;gap:8px;margin-bottom:12px;flex-wrap:wrap}
.f{background:var(--panel);border:1px solid var(--line);color:var(--mut);font-size:11.5px;padding:6px 10px;border-radius:6px;cursor:pointer}
.f.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.sp{flex:1}
.hint{font-size:11px;color:var(--mut)}
.bars{display:flex;flex-direction:column;gap:6px}
.bar-row{display:grid;grid-template-columns:200px 1fr 80px;align-items:center;gap:10px;font-size:12px}
.br-name small{display:block;color:var(--mut);font-size:10.5px;font-weight:400}
.br-track{position:relative;height:14px;background:var(--panel2);border-radius:3px}
.br-mid{position:absolute;left:50%;top:0;bottom:0;width:1px;background:var(--line)}
.br-fill{position:absolute;top:0;bottom:0;border-radius:3px}
.br-fill.p{left:50%;background:var(--pos)}
.br-fill.n{right:50%;background:var(--neg)}
.br-val{text-align:right;font-weight:700}
.dgrid{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
.dept{display:flex;justify-content:space-between;align-items:center;background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:10px 14px}
.d-name{font-size:12.5px;font-weight:600}
.d-name a{color:inherit;text-decoration:none}
.d-meta{font-size:11px;color:var(--mut);margin:2px 0 6px}
.d-mini{position:relative;height:6px;background:var(--panel2);border-radius:3px;width:160px}
.d-mini i{position:absolute;top:0;bottom:0;border-radius:3px}
.d-val{font-weight:700;font-size:13px}
.tbl{width:100%;border-collapse:collapse;font-size:12px}
.tbl th{text-align:left;color:var(--mut);font-weight:600;font-size:11px;text-transform:uppercase;padding:6px 8px;border-bottom:1px solid var(--line)}
.tbl td{padding:8px;border-bottom:1px solid var(--line)}
.tbl .rt{text-align:right}
.tbl .mono{font-variant-numeric:tabular-nums}
.badge{background:var(--panel2);border:1px solid var(--line);color:var(--mut);font-size:10.5px;padding:2px 8px;border-radius:20px}
footer{font-size:11px;color:var(--mut);border-top:1px solid var(--line);padding-top:16px;margin-top:8px}
</style>
</head><body>
<div class="wrap">

<header>
  <div>
    <div class="eyebrow">Fucape Business School · Extrato Secullum</div>
    <h1>Banco de Horas <span>/ {{ escopo_titulo }}</span></h1>
  </div>
  <div class="meta">
    Período <b>{{ periodo_texto }}</b><br>
    Emitido <b>{{ data_emissao }}</b> · {{ r.contadores.total }} colaboradores<br>
    <b>{{ r.contadores.elegiveis }} elegíveis</b> ao ponto · <b>{{ r.contadores.nao_elegiveis }} fora</b> (isentos/config)
  </div>
</header>

<div class="hero">
  <div class="hero-top">
    <div class="hero-label">Saldo líquido consolidado · base elegível</div>
    <div class="hero-note">exclui {{ r.contadores.nao_elegiveis }} registros sem batida de ponto</div>
  </div>
  <div style="font-size:40px;font-weight:800;letter-spacing:-.03em;color:{{ 'var(--pos)' if r.gauge.saldo_liquido_min >= 0 else 'var(--neg)' }}">{{ r.gauge.saldo_liquido_fmt }}</div>
  <div style="font-size:12.5px;color:var(--mut);margin-top:2px">{{ r.gauge.nota_hero }}</div>
  <div class="gauge">
    <div class="seg neg" style="width:{{ '%.4f'|format(r.gauge.neg_pct) }}%"><b>{{ r.gauge.neg_fmt }}</b></div>
    <div class="seg pos" style="width:{{ '%.4f'|format(r.gauge.pos_pct) }}%"><b>{{ r.gauge.pos_fmt }}</b></div>
    <div class="divider" style="left:{{ '%.4f'|format(r.gauge.neg_pct) }}%"></div>
  </div>
  <div class="gauge-legend">
    <span class="l">&#9668; {{ r.gauge.qtd_receber }} credores da empresa (devem horas)</span>
    <span class="r">{{ r.gauge.qtd_passivo }} credores de horas (a empresa deve) &#9658;</span>
  </div>
</div>

<div class="kpis">
  <div class="kpi p"><div class="k-val tpos">{{ r.kpis.passivo.valor_fmt }}</div><div class="k-lab">Passivo de horas<br>(a empresa deve pagar/folgar)</div><div class="k-sub">{{ r.kpis.passivo.sub }}</div></div>
  <div class="kpi n"><div class="k-val tneg">{{ r.kpis.receber.valor_fmt }}</div><div class="k-lab">A empresa tem a receber<br>(devem horas)</div><div class="k-sub">{{ r.kpis.receber.sub }}</div></div>
  <div class="kpi a"><div class="k-val" style="color:var(--amber)">{{ r.kpis.concentracao.valor_fmt }}</div><div class="k-lab">Concentração de risco<br>{{ r.kpis.concentracao.pct_fmt }} do passivo</div><div class="k-sub">{{ r.kpis.concentracao.sub }}</div></div>
  <div class="kpi b"><div class="k-val" style="color:var(--blue)">{{ r.kpis.nao_elegiveis.valor }}</div><div class="k-lab">Registros não elegíveis<br>débito padrão &#8805;300h</div><div class="k-sub">{{ r.kpis.nao_elegiveis.sub }}</div></div>
</div>

{% if r.alerta %}
<div class="alert"><b>Leitura de dado, não de gente.</b> {{ r.alerta }}</div>
{% endif %}

<section>
  <div class="s-head"><span class="idx">01</span><h2>Ranking individual</h2></div>
  <div class="s-sub">Saldo acumulado no período por colaborador com ponto ativo. Verde = a empresa deve a ele; vermelho = ele deve à empresa.</div>
  <div class="controls">
    <button class="f on" data-f="all">Todos ({{ r.contadores.elegiveis }})</button>
    <button class="f" data-f="pos">Só credores ({{ r.gauge.qtd_passivo }})</button>
    <button class="f" data-f="neg">Só devedores ({{ r.gauge.qtd_receber }})</button>
    <div class="sp"></div>
    <span class="hint">passe o mouse para detalhe · escala cortada em &plusmn;40h p/ leitura*</span>
  </div>
  <div class="bars" id="bars">
    {% for pessoa in r.ranking %}
    <div class="bar-row" title="{{ pessoa.tooltip }}">
      <div class="br-name">{{ pessoa.nome }}<small>{{ pessoa.subtitulo }}</small></div>
      <div class="br-track"><div class="br-mid"></div>
        <div class="br-fill {{ pessoa.classe }}" style="width:{{ '%.4f'|format(pessoa.pct) }}%"></div></div>
      <div class="br-val {{ 'tpos' if pessoa.classe == 'p' else 'tneg' }}">{{ pessoa.valor_fmt }}</div>
    </div>
    {% endfor %}
  </div>
  {% if r.nota_ranking %}<div class="hint" style="margin-top:8px">{{ r.nota_ranking }}</div>{% endif %}
</section>

{% if mostrar_deptos %}
<section>
  <div class="s-head"><span class="idx">02</span><h2>Saldo por departamento</h2></div>
  <div class="s-sub">Onde o passivo se acumula e onde a empresa está no positivo. Atenção aos negativos: são áreas com folga a compensar ou sobrecarga não paga.</div>
  <div class="dgrid">
    {% for d in r.deptos %}
    <div class="dept">
      <div class="d-l">
        <div class="d-name"><a href="deptos/{{ d.slug }}.html">{{ d.nome }}</a></div>
        <div class="d-meta">{{ d.pessoas }} pessoa{{ 's' if d.pessoas != 1 else '' }} · média {{ d.media_fmt }}</div>
        <div class="d-mini"><i style="width:{{ '%.4f'|format(d.mini_pct) }}%;background:{{ 'var(--pos)' if d.total_min >= 0 else 'var(--neg)' }};{{ 'left:0' if d.total_min >= 0 else 'right:0' }}"></i></div>
      </div>
      <div class="d-val {{ 'tpos' if d.total_min >= 0 else 'tneg' }}">{{ d.valor_fmt }}</div>
    </div>
    {% endfor %}
  </div>
</section>
{% endif %}

{% if r.nao_elegiveis_lista %}
<section>
  <div class="s-head"><span class="idx">03</span><h2>Fora da base · revisar configuração</h2></div>
  <div class="s-sub">Registros com débito padrão automático. Ação sugerida: definir no Secullum quem é isento de ponto (cargo de confiança) e corrigir a jornada dos que deveriam bater.</div>
  <table class="tbl">
    <thead><tr><th>Colaborador</th><th>Função</th><th>Depto</th><th class="rt">Saldo bruto</th><th class="rt">Status</th></tr></thead>
    <tbody>
      {% for p in r.nao_elegiveis_lista %}
      <tr><td class="nm">{{ p.nome }}</td><td>{{ p.funcao }}</td><td>{{ p.departamento }}</td>
      <td class="rt mono">{{ p.valor_fmt }}</td>
      <td class="rt"><span class="badge">config</span></td></tr>
      {% endfor %}
    </tbody>
  </table>
</section>
{% endif %}

<footer>
  <b>Metodologia.</b> Fonte: Extrato do Banco de Horas Secullum Ponto Web, período {{ periodo_texto }}.
  Saldos somados a partir do total mensal de cada colaborador. "Elegível" = possui batidas reais no período.
  "Não elegível" = débito padrão &#8805; 300h sem crédito, indicando isenção ou jornada mal configurada.<br>
  <b>Limite de leitura.</b> Banco de horas mede presença registrada, não produtividade nem entrega. Use como sinal de gestão de jornada e compliance, cruzando com desempenho antes de qualquer decisão sobre pessoas.
</footer>

</div>
<script>
document.querySelectorAll('.controls .f').forEach(function(btn){
  btn.addEventListener('click', function(){
    document.querySelectorAll('.controls .f').forEach(function(b){ b.classList.remove('on'); });
    btn.classList.add('on');
    var filtro = btn.dataset.f;
    document.querySelectorAll('#bars .bar-row').forEach(function(row){
      var preenchimento = row.querySelector('.br-fill');
      var ehPositivo = preenchimento.classList.contains('p');
      var mostrar = filtro === 'all' || (filtro === 'pos' && ehPositivo) || (filtro === 'neg' && !ehPositivo);
      row.style.display = mostrar ? '' : 'none';
    });
  });
});
</script>
</body></html>
```

- [ ] **Step 2: Write the failing test**

`tests/test_template.py`:
```python
from painel_horas.calculos import montar_relatorio
from painel_horas.parser import Colaborador, Mes
from painel_horas.template import render_pagina
import datetime


def _colab_simples(nome, departamento, valor_min):
    return Colaborador(
        nome=nome, funcao="Cargo", admissao=datetime.date(2020, 1, 1), departamento=departamento,
        meses=[Mes(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), valor_min, max(valor_min, 0), max(-valor_min, 0), 0)],
        total_bruto_min=valor_min, credito_total_min=max(valor_min, 0), debito_total_min=max(-valor_min, 0),
    )


def test_render_pagina_geral_contem_secoes_esperadas():
    r = montar_relatorio([_colab_simples("Fulano", "TECNOLOGIA", 100)], escopo="geral")
    html = render_pagina({
        "escopo_titulo": "Painel do CEO", "periodo_texto": "01/01/2026 → 09/07/2026",
        "data_emissao": "10/07/2026", "mostrar_deptos": True, "r": r,
    })
    assert "<!DOCTYPE html>" in html
    assert "Painel do CEO" in html
    assert "Fulano" in html
    assert "Saldo por departamento" in html
    assert "deptos/tecnologia.html" in html
    assert "<script>" in html and "<link" not in html


def test_render_pagina_depto_omite_secao_deptos():
    r = montar_relatorio([_colab_simples("Ciclano", "BIBLIOTECA", -50)], escopo="depto")
    html = render_pagina({
        "escopo_titulo": "Painel Biblioteca", "periodo_texto": "01/01/2026 → 09/07/2026",
        "data_emissao": "10/07/2026", "mostrar_deptos": False, "r": r,
    })
    assert "Saldo por departamento" not in html
    assert "Ciclano" in html
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_template.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'painel_horas.template'`

- [ ] **Step 4: Write minimal implementation**

`painel_horas/template.py`:
```python
import pathlib

from jinja2 import Environment, FileSystemLoader, select_autoescape

_DIR_TEMPLATES = pathlib.Path(__file__).resolve().parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_DIR_TEMPLATES)),
    autoescape=select_autoescape(["html"]),
)


def render_pagina(contexto: dict) -> str:
    template = _env.get_template("painel.html.j2")
    return template.render(**contexto)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_template.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add templates/painel.html.j2 painel_horas/template.py tests/test_template.py
git commit -m "feat: add self-contained dashboard template and renderer"
```

---

### Task 7: Orchestration script (`atualizar_painel.py`)

**Files:**
- Create: `atualizar_painel.py`
- Test: `tests/test_atualizar_painel.py`

**Interfaces:**
- Consumes: `ler_colaboradores` (parser.py), `montar_relatorio`, `dept_label`, `CSC_LABEL` (calculos.py), `slugify` (slug.py), `render_pagina` (template.py).
- Produces: `encontrar_xlsx_mais_recente(pasta: pathlib.Path) -> pathlib.Path | None`, `gerar_painel(caminho_xlsx: pathlib.Path, pasta_saida: pathlib.Path) -> dict` (pure, no browser/side-effects beyond writing files — testable), `main()` (CLI entrypoint that also opens the browser).

- [ ] **Step 1: Write the failing test**

`tests/test_atualizar_painel.py`:
```python
import datetime
from pathlib import Path

from atualizar_painel import encontrar_xlsx_mais_recente, gerar_painel


def test_encontrar_xlsx_mais_recente_vazio(tmp_path):
    assert encontrar_xlsx_mais_recente(tmp_path) is None


def test_encontrar_xlsx_mais_recente_escolhe_o_mais_novo(tmp_path):
    antigo = tmp_path / "antigo.xlsx"
    novo = tmp_path / "novo.xlsx"
    antigo.write_bytes(b"x")
    novo.write_bytes(b"y")
    import os
    import time
    os.utime(antigo, (time.time() - 100, time.time() - 100))
    assert encontrar_xlsx_mais_recente(tmp_path) == novo


def test_gerar_painel_cria_index_e_paginas_de_departamento(tmp_path, workbook_path):
    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "meses": [("01/06/2026 até 30/06/2026", datetime.timedelta(hours=5),
                       datetime.timedelta(hours=5), datetime.timedelta(0), datetime.timedelta(0))],
            "total": (datetime.timedelta(hours=5), datetime.timedelta(hours=5), datetime.timedelta(0), datetime.timedelta(0)),
        },
        {
            "nome": "PESSOA CONTROLADORIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "CONTROLADORIA",
            "meses": [("01/06/2026 até 30/06/2026", datetime.timedelta(hours=-2),
                       datetime.timedelta(0), datetime.timedelta(hours=2), datetime.timedelta(0))],
            "total": ("-02:00", datetime.timedelta(0), datetime.timedelta(hours=2), datetime.timedelta(0)),
        },
        {
            "nome": "PESSOA COMERCIAL", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "COMERCIAL",
            "meses": [("01/06/2026 até 30/06/2026", datetime.timedelta(hours=1),
                       datetime.timedelta(hours=1), datetime.timedelta(0), datetime.timedelta(0))],
            "total": (datetime.timedelta(hours=1), datetime.timedelta(hours=1), datetime.timedelta(0), datetime.timedelta(0)),
        },
    ])
    pasta_saida = tmp_path / "painel"

    resumo = gerar_painel(caminho, pasta_saida)

    assert resumo["colaboradores"] == 3
    assert resumo["departamentos"] == 2  # Tecnologia + CSC (Controladoria+Comercial)
    assert (pasta_saida / "index.html").exists()
    assert (pasta_saida / "deptos" / "tecnologia.html").exists()
    assert (pasta_saida / "deptos" / "centro-servicos-compartilhados.html").exists()
    assert not (pasta_saida / "deptos" / "controladoria.html").exists()

    conteudo_csc = (pasta_saida / "deptos" / "centro-servicos-compartilhados.html").read_text(encoding="utf-8")
    assert "PESSOA CONTROLADORIA" in conteudo_csc
    assert "PESSOA COMERCIAL" in conteudo_csc
    # subtexto de rastreabilidade do time original
    assert "Controladoria" in conteudo_csc
    assert "Comercial" in conteudo_csc


def test_main_sem_xlsx_nao_gera_nada_e_avisa(tmp_path, monkeypatch, capsys):
    import atualizar_painel
    monkeypatch.setattr(atualizar_painel, "__file__", str(tmp_path / "atualizar_painel.py"))
    (tmp_path / "extratos").mkdir()

    atualizar_painel.main()

    saida = capsys.readouterr()
    assert "erro" in saida.out
    assert not (tmp_path / "painel").exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_atualizar_painel.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'atualizar_painel'`

- [ ] **Step 3: Write minimal implementation**

`atualizar_painel.py`:
```python
import webbrowser
from datetime import date
from pathlib import Path

from painel_horas.calculos import CSC_LABEL, dept_label, montar_relatorio
from painel_horas.parser import ler_colaboradores
from painel_horas.slug import slugify
from painel_horas.template import render_pagina


def encontrar_xlsx_mais_recente(pasta: Path) -> Path | None:
    arquivos = list(pasta.glob("*.xlsx"))
    if not arquivos:
        return None
    return max(arquivos, key=lambda p: p.stat().st_mtime)


def _periodo_texto(colaboradores) -> str:
    todas_inicio = [m.inicio for c in colaboradores for m in c.meses]
    todas_fim = [m.fim for c in colaboradores for m in c.meses]
    if not todas_inicio:
        return ""
    return f"{min(todas_inicio).strftime('%d/%m/%Y')} → {max(todas_fim).strftime('%d/%m/%Y')}"


def _agrupar_por_departamento(colaboradores) -> dict:
    grupos: dict[str, list] = {}
    for c in colaboradores:
        grupos.setdefault(dept_label(c.departamento), []).append(c)
    return grupos


def gerar_painel(caminho_xlsx: Path, pasta_saida: Path) -> dict:
    colaboradores = ler_colaboradores(caminho_xlsx)
    periodo_texto = _periodo_texto(colaboradores)
    data_emissao = date.today().strftime("%d/%m/%Y")

    pasta_saida.mkdir(parents=True, exist_ok=True)
    pasta_deptos = pasta_saida / "deptos"
    pasta_deptos.mkdir(exist_ok=True)

    relatorio_geral = montar_relatorio(colaboradores, escopo="geral")
    html_geral = render_pagina({
        "escopo_titulo": "Painel do CEO",
        "periodo_texto": periodo_texto,
        "data_emissao": data_emissao,
        "mostrar_deptos": True,
        "r": relatorio_geral,
    })
    (pasta_saida / "index.html").write_text(html_geral, encoding="utf-8")

    grupos = _agrupar_por_departamento(colaboradores)
    for label, membros in grupos.items():
        escopo = "csc" if label == CSC_LABEL else "depto"
        relatorio = montar_relatorio(membros, escopo=escopo)
        html = render_pagina({
            "escopo_titulo": f"Painel {label}",
            "periodo_texto": periodo_texto,
            "data_emissao": data_emissao,
            "mostrar_deptos": False,
            "r": relatorio,
        })
        (pasta_deptos / f"{slugify(label)}.html").write_text(html, encoding="utf-8")

    return {
        "colaboradores": len(colaboradores),
        "departamentos": len(grupos),
        "elegiveis": relatorio_geral["contadores"]["elegiveis"],
        "nao_elegiveis": relatorio_geral["contadores"]["nao_elegiveis"],
    }


def main() -> None:
    raiz = Path(__file__).resolve().parent
    pasta_extratos = raiz / "extratos"
    pasta_saida = raiz / "painel"

    xlsx = encontrar_xlsx_mais_recente(pasta_extratos)
    if xlsx is None:
        print(f"[erro] nenhum arquivo .xlsx encontrado em {pasta_extratos} — nada foi gerado.")
        return

    resumo = gerar_painel(xlsx, pasta_saida)
    print(f"Painel atualizado: {resumo['colaboradores']} colaboradores, {resumo['departamentos']} departamentos")
    print(f"  {resumo['elegiveis']} elegíveis · {resumo['nao_elegiveis']} fora da base")

    webbrowser.open((pasta_saida / "index.html").resolve().as_uri())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_atualizar_painel.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Run full test suite**

Run: `pytest -v`
Expected: PASS (all tests across all modules, ~33 tests)

- [ ] **Step 6: Commit**

```bash
git add atualizar_painel.py tests/test_atualizar_painel.py
git commit -m "feat: add atualizar_painel.py orchestration script"
```

---

### Task 8: Manual smoke test with the real extract

**Files:**
- Modify: none (manual verification step, no code changes)

**Interfaces:**
- Consumes: `gerar_painel` from `atualizar_painel.py`, the real `ExtratoBancoHoras.xlsx` already present at the repo root.

- [ ] **Step 1: Copy the real xlsx into `extratos/`**

Run: `cp ExtratoBancoHoras.xlsx extratos/ExtratoBancoHoras.xlsx` (PowerShell: `Copy-Item ExtratoBancoHoras.xlsx extratos/`)
Expected: file now present at `extratos/ExtratoBancoHoras.xlsx` (gitignored, won't be committed).

- [ ] **Step 2: Run the real script**

Run: `python atualizar_painel.py`
Expected: console prints `Painel atualizado: 44 colaboradores, 13 departamentos` followed by `35 elegíveis · 9 fora da base` (or close, matching the current xlsx snapshot), and the default browser opens `painel/index.html`.

- [ ] **Step 3: Visually inspect `painel/index.html`**

Check: hero gauge renders with a plausible green/red split, KPI cards show 4 values, ranking bars list all eligible employees sorted by balance, department grid links resolve to `painel/deptos/*.html`, section 03 table lists exactly the "config/isento" employees.

- [ ] **Step 4: Visually inspect one department page, e.g. `painel/deptos/centro-servicos-compartilhados.html`**

Check: only Controladoria/Comercial/Financeiro employees appear, each ranking row's subtitle shows their original sub-team name, KPIs/gauge are recomputed for this scope only, section 02 (department grid) is absent.

- [ ] **Step 5: Report findings to the user**

If colors/contrast need adjustment (expected per spec — the original stylesheet was unrecoverable), note specific requested tweaks; do not commit `painel/` (gitignored) or the copied xlsx.

---

## Self-Review Notes

- **Spec coverage:** header/meta ✓ (Task 6), hero gauge ✓, 4 KPIs ✓, alert box ✓, ranking with filters ✓, department grid (index-only) ✓, "fora da base" table ✓, footer ✓, CSC merge ✓, auto-slug for unseen departments ✓ (Task 3, no hardcoded list), timedelta/string hour parsing ✓ (Task 2/4), malformed-block fallback ✓ (Task 4), empty-`extratos/`/no-xlsx guard ✓ (Task 7), console summary + browser open ✓ (Task 7), `.bat` entrypoint ✓ (Task 1).
- **Known deliberate deviations from the lost original stylesheet:** color palette, KPI card copy for "concentração de risco" and "não elegíveis" subtext were rewritten as data-driven/generic text instead of the narrative phrasing in the reference artifact (e.g. no fabricated claims like "ajustes atípicos" or "Inclui você (CEO)" that can't be derived from data). Flagged for the user in Task 8.
