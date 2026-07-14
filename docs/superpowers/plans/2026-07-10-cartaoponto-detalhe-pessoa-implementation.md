# Cartão Ponto como fonte de verdade + Página de detalhe por colaborador — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `ExtratoBancoHoras.xlsx` with `cartaoponto.xlsx` (Secullum punch-card export, day-by-day) as the painel's only data source, and add a per-employee detail page (monthly/weekly summary + full daily punch table + best/worst highlights) linked from every employee name in the ranking.

**Architecture:** Same pipeline shape as today (`parser.py` → `calculos.py` → `template.py` → `atualizar_painel.py`), but `parser.py` is rewritten for the cartaoponto block format (`Dia`/`Colaborador.dias` instead of `Mes`), `calculos.py` gets a new eligibility rule and new monthly/weekly/highlight aggregations, and a new `pessoa.html.j2` template + `deptos/pessoas/<slug>.html` output are added. All existing dark-theme visual language and Jinja2/no-server architecture are reused as-is.

**Tech Stack:** Python 3.12, openpyxl, Jinja2, pytest. No new dependencies.

## Global Constraints

- Reference spec: `docs/superpowers/specs/2026-07-10-cartaoponto-detalhe-pessoa-design.md`. Prior spec `docs/superpowers/specs/2026-07-10-painel-horas-fucape-design.md` still governs layout/KPIs/CSC-grouping/distribution — not repeated here, not to be changed by this plan except where noted.
- `cartaoponto.xlsx` goes in `extratos/` — same discovery mechanism (`encontrar_xlsx_mais_recente`) as today, no change to that function.
- Old `ExtratoBancoHoras.xlsx`-specific parsing (`NOME:`/`PERÍODO` markers, `Mes` dataclass, crédito/débito heuristic) is deleted, not kept alongside the new code.
- Every generated HTML file must remain self-contained (inline CSS + JS, `autoescape=True`, no external `<link>`).
- Person pages go in `painel/deptos/pessoas/<slug>.html`, one per colaborador with at least 1 real punch in the period; colaboradores with zero real punches get no page and no link.
- Week = Monday–Sunday.
- Run `python -m pytest` from the repo root after every task; all tests must pass before moving to the next task.

---

### Task 1: `horas.py` — support explicit `"+HH:MM"` strings

**Files:**
- Modify: `painel_horas/horas.py`
- Test: `tests/test_horas.py`

**Interfaces:**
- Produces: `parse_horas(valor) -> int` now also accepts strings with a leading `"+"` (in addition to `timedelta`, bare `"HH:MM"`, and `"-HH:MM"` it already handles).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_horas.py`:

```python
def test_parse_horas_string_positiva_com_sinal_explicito():
    assert parse_horas("+00:12") == 12


def test_parse_horas_string_positiva_grande_com_sinal_explicito():
    assert parse_horas("+112:55") == 6775
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_horas.py -v`
Expected: the two new tests FAIL (`+00:12` currently raises `ValueError` from `int("+00")` — actually `int()` accepts a leading `+`, but `horas_str.split(":")` on `"+00:12"` after only stripping `"-"` leaves the `+` in `horas_str`, which `int()` *does* parse fine — the real failure is that `total` never gets negated-back correctly is not the issue; confirm by running and reading the actual error before assuming).

- [ ] **Step 3: Update `parse_horas` to strip both signs**

In `painel_horas/horas.py`, change:

```python
        texto = valor.strip()
        negativo = texto.startswith("-")
        texto = texto.lstrip("-")
```

to:

```python
        texto = valor.strip()
        negativo = texto.startswith("-")
        texto = texto.lstrip("+-")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_horas.py -v`
Expected: PASS (all tests in the file, including the pre-existing ones)

- [ ] **Step 5: Commit**

```bash
git add painel_horas/horas.py tests/test_horas.py
git commit -m "feat: parse_horas accepts explicit +HH:MM strings"
```

---

### Task 2: `parser.py` rewrite for cartaoponto format + new test fixture

**Files:**
- Modify: `painel_horas/parser.py` (full rewrite)
- Modify: `tests/conftest.py` (full rewrite of `workbook_path` fixture)
- Modify: `tests/test_parser.py` (full rewrite)

**Interfaces:**
- Produces:
  - `Dia` dataclass: `data: date`, `dia_semana: str`, `ent1/sai1/ent2/sai2/ent3/sai3: object` (each a `datetime.timedelta`, `str` status code, or `None`), `ex50_min: int`, `atraso_min: int`, `btotal_min: int | None`, `exnot_min: int`.
  - `Colaborador` dataclass: `nome: str`, `funcao: str`, `admissao: date | None`, `departamento: str`, `dias: list[Dia]`, `total_bruto_min: int`.
  - `ler_colaboradores(caminho_xlsx) -> list[Colaborador]`.
- Consumes: `parse_horas` from Task 1.

Real-file layout confirmed by direct inspection of `cartaoponto.xlsx` (row offsets relative to the row where column 1 == `"Nome"`, call it `r`): `Admissão` value is at `(r+2, col 5)`; `Função` value at `(r+3, col 2)`; `Departamento` value at `(r+4, col 2)`; the daily table header (`"Data"` in col 1) is a few rows further down (search `r+5..r+15`); the `"Totais"` row is immediately below the header; daily rows start right after `"Totais"` and each has col 1 formatted `"DD/MM/AAAA - Xxx"` — the block ends at the first row whose col 1 doesn't match that pattern (no fixed block length).

- [ ] **Step 1: Rewrite `tests/conftest.py`**

```python
import openpyxl
import pytest


@pytest.fixture
def workbook_path(tmp_path):
    def _construir(blocos):
        """`blocos` é uma lista de dicts com chaves:
        nome, funcao, admissao, departamento, dias.
        `dias` é uma lista de tuplas de 12 elementos:
        (data_str "DD/MM/AAAA", sufixo_dia_semana, ent1, sai1, ent2, sai2, ent3, sai3,
         ex50, atraso, btotal, exnot).
        Batidas (ent/sai) são datetime.timedelta (hora real), str (código de status,
        ex: "FALTA") ou None. ex50/atraso/exnot são datetime.timedelta ou None.
        btotal é string "+HH:MM"/"-HH:MM" ou None — nunca int/float cru (o xlsx real
        nunca guarda isso)."""
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Sheet1"
        linha = 1
        for bloco in blocos:
            ws.cell(row=linha, column=1, value="CARTÃO PONTO")
            ws.cell(row=linha + 1, column=1, value="Período: 01/01/2026 até 09/07/2026.")
            ws.cell(row=linha + 3, column=1, value="Empresa")
            ws.cell(row=linha + 3, column=2, value="FUCAPE PESQUISA E ENSINO SA")
            ws.cell(row=linha + 4, column=1, value="CNPJ")
            ws.cell(row=linha + 5, column=1, value="Inscrição")
            ws.cell(row=linha + 5, column=2, value="ISENTO")
            ws.cell(row=linha + 7, column=1, value="Nome")
            ws.cell(row=linha + 7, column=2, value=bloco["nome"])
            ws.cell(row=linha + 8, column=1, value="Nº Identificador")
            ws.cell(row=linha + 9, column=1, value="C.T.P.S.")
            ws.cell(row=linha + 9, column=4, value="Admissão")
            ws.cell(row=linha + 9, column=5, value=bloco["admissao"] or "")
            ws.cell(row=linha + 10, column=1, value="Função")
            ws.cell(row=linha + 10, column=2, value=bloco["funcao"])
            ws.cell(row=linha + 11, column=1, value="Departamento")
            ws.cell(row=linha + 11, column=2, value=bloco["departamento"] or "")
            ws.cell(row=linha + 12, column=1, value="Observação")

            header_row = linha + 15  # Nome (linha+7) + offset 8, igual ao arquivo real
            ws.cell(row=header_row, column=1, value="Data")
            totais_row = header_row + 1
            ws.cell(row=totais_row, column=1, value="Totais")

            r = totais_row + 1
            for dia in bloco["dias"]:
                data_str, sufixo, ent1, sai1, ent2, sai2, ent3, sai3, ex50, atraso, btotal, exnot = dia
                ws.cell(row=r, column=1, value=f"{data_str} - {sufixo}")
                ws.cell(row=r, column=2, value=ent1)
                ws.cell(row=r, column=3, value=sai1)
                ws.cell(row=r, column=4, value=ent2)
                ws.cell(row=r, column=5, value=sai2)
                ws.cell(row=r, column=6, value=ent3)
                ws.cell(row=r, column=7, value=sai3)
                ws.cell(row=r, column=8, value=ex50)
                ws.cell(row=r, column=9, value=atraso)
                ws.cell(row=r, column=10, value=btotal)
                ws.cell(row=r, column=11, value=exnot)
                r += 1

            linha = r + 10  # espaço em branco antes do próximo bloco (legenda/assinatura no arquivo real)
        caminho = tmp_path / "cartaoponto_teste.xlsx"
        wb.save(caminho)
        return caminho
    return _construir
```

- [ ] **Step 2: Rewrite `tests/test_parser.py` (failing against the old parser)**

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
            "dias": [
                ("11/05/2026", "Seg", datetime.timedelta(hours=8), datetime.timedelta(hours=12),
                 datetime.timedelta(hours=13), datetime.timedelta(hours=18), None, None,
                 datetime.timedelta(0), datetime.timedelta(0), "+00:12", datetime.timedelta(0)),
                ("12/05/2026", "Ter", "FALTA", "FALTA", None, None, None, None,
                 None, None, None, None),
            ],
        },
    ])

    colaboradores = ler_colaboradores(caminho)

    assert len(colaboradores) == 1
    c = colaboradores[0]
    assert c.nome == "ANA CARLA CRISTOVAO DA SILVA"
    assert c.funcao == "ASSISTENTE DE COORDENAÇÃO"
    assert c.admissao == datetime.date(2026, 5, 13)
    assert c.departamento == "COORDENAÇÃO DE CURSO"
    assert len(c.dias) == 2
    assert c.dias[0].data == datetime.date(2026, 5, 11)
    assert c.dias[0].dia_semana == "Seg"
    assert c.dias[0].btotal_min == 12
    assert c.dias[1].data == datetime.date(2026, 5, 12)
    assert c.dias[1].btotal_min is None
    assert c.dias[1].ent1 == "FALTA"
    assert c.total_bruto_min == 12


def test_ler_colaboradores_bloco_incompleto_usa_fallback(workbook_path, capsys):
    caminho = workbook_path([
        {
            "nome": "FULANO SEM DADOS",
            "funcao": "ESTAGIARIO",
            "admissao": None,
            "departamento": None,
            "dias": [
                ("01/06/2026", "Seg", datetime.timedelta(hours=8), datetime.timedelta(hours=17),
                 None, None, None, None, None, None, "+00:00", None),
            ],
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
            "dias": [("01/06/2026", "Seg", datetime.timedelta(hours=8), datetime.timedelta(hours=17),
                      None, None, None, None, None, None, "+01:00", None)],
        },
        {
            "nome": "PESSOA DOIS", "funcao": "CARGO B", "admissao": "01/02/2020",
            "departamento": "BIBLIOTECA",
            "dias": [("01/06/2026", "Seg", datetime.timedelta(hours=8), datetime.timedelta(hours=17),
                      None, None, None, None, None, None, "-01:00", None)],
        },
    ])

    colaboradores = ler_colaboradores(caminho)

    assert [c.nome for c in colaboradores] == ["PESSOA UM", "PESSOA DOIS"]
    assert colaboradores[0].departamento == "TECNOLOGIA"
    assert colaboradores[1].departamento == "BIBLIOTECA"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/test_parser.py -v`
Expected: FAIL (old parser looks for `"NOME:"`-prefixed strings, finds nothing in the new fixture shape)

- [ ] **Step 4: Rewrite `painel_horas/parser.py`**

```python
import re
from dataclasses import dataclass, field
from datetime import date

import openpyxl

from painel_horas.horas import parse_horas

_PADRAO_DIA = re.compile(r"^(\d{2}/\d{2}/\d{4}) - (.+)$")


@dataclass
class Dia:
    data: date
    dia_semana: str
    ent1: object
    sai1: object
    ent2: object
    sai2: object
    ent3: object
    sai3: object
    ex50_min: int
    atraso_min: int
    btotal_min: int | None
    exnot_min: int


@dataclass
class Colaborador:
    nome: str
    funcao: str
    admissao: date | None
    departamento: str
    dias: list[Dia] = field(default_factory=list)
    total_bruto_min: int = 0


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
        if val(r, 1) != "Nome":
            r += 1
            continue

        nome_bruto = val(r, 2)
        nome = nome_bruto.strip() if isinstance(nome_bruto, str) else ""
        if not nome:
            print(f"[aviso] bloco na linha {r} sem nome reconhecível — pulando")
            r += 1
            continue

        admissao_str = val(r + 2, 5)
        admissao = (
            _parse_data(admissao_str)
            if isinstance(admissao_str, str) and admissao_str.strip()
            else None
        )
        funcao_bruta = val(r + 3, 2)
        funcao = funcao_bruta.strip() if isinstance(funcao_bruta, str) else ""
        departamento_bruto = val(r + 4, 2)
        departamento = (
            departamento_bruto.strip()
            if isinstance(departamento_bruto, str) and departamento_bruto.strip()
            else "Sem Departamento"
        )
        if admissao is None or departamento == "Sem Departamento":
            print(f"[aviso] colaborador '{nome}' com admissão/departamento incompleto — usando fallback")

        header_row = None
        limite = min(max_row, r + 15)
        j = r + 5
        while j <= limite:
            if val(j, 1) == "Data":
                header_row = j
                break
            j += 1

        dias: list[Dia] = []
        if header_row is None:
            print(f"[aviso] colaborador '{nome}' sem tabela diária reconhecível — pulando dias")
            k = r + 1
        else:
            k = header_row + 2  # pula a linha "Totais"
            while k <= max_row:
                bruto = val(k, 1)
                m = _PADRAO_DIA.match(bruto) if isinstance(bruto, str) else None
                if not m:
                    break
                btotal_raw = val(k, 10)
                dias.append(Dia(
                    data=_parse_data(m.group(1)),
                    dia_semana=m.group(2),
                    ent1=val(k, 2), sai1=val(k, 3),
                    ent2=val(k, 4), sai2=val(k, 5),
                    ent3=val(k, 6), sai3=val(k, 7),
                    ex50_min=parse_horas(val(k, 8)),
                    atraso_min=parse_horas(val(k, 9)),
                    btotal_min=parse_horas(btotal_raw) if btotal_raw is not None else None,
                    exnot_min=parse_horas(val(k, 11)),
                ))
                k += 1

        total_bruto = sum(d.btotal_min or 0 for d in dias)
        colaboradores.append(Colaborador(
            nome=nome, funcao=funcao, admissao=admissao, departamento=departamento,
            dias=dias, total_bruto_min=total_bruto,
        ))
        r = k

    return colaboradores
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_parser.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add painel_horas/parser.py tests/conftest.py tests/test_parser.py
git commit -m "feat: rewrite parser for cartaoponto punch-card format"
```

---

### Task 3: `calculos.py` — eligibility rule + saldo + ranking (drop old heuristic)

**Files:**
- Modify: `painel_horas/calculos.py`
- Modify: `tests/test_calculos.py` (rewrite the parts touching `Mes`/`is_config`)

**Interfaces:**
- Consumes: `Colaborador`, `Dia` from Task 2.
- Produces:
  - `sem_batida_real(colab) -> bool` (replaces `is_config`)
  - `saldo_trabalhado_min(colab) -> int` (same name, now day-based)
  - `montar_relatorio(colaboradores, escopo="geral", prefixo_pessoas="") -> dict` — same shape as before plus each `ranking[i]` dict now also has `"pessoa_href"`.
  - `dept_label`, `_pct_ranking`, `_tooltip`, `_subtitulo`, `CSC_ORIGENS`, `CSC_LABEL`, `ESCALA_RANKING_MAX_MIN` unchanged (kept as-is for Task 4/5/6 to rely on).

- [ ] **Step 1: Rewrite `tests/test_calculos.py`**

Replace the whole file with:

```python
import datetime
from painel_horas.parser import Colaborador, Dia
from painel_horas.calculos import (
    dept_label, saldo_trabalhado_min, sem_batida_real, montar_relatorio,
)


def _dia(data, btotal_min=None, com_batida=True):
    """Cria um Dia de teste. com_batida=True simula uma hora real de entrada;
    com_batida=False simula um código de status (sem batida real nesse dia)."""
    ent1 = datetime.timedelta(hours=8) if com_batida else "FALTA"
    return Dia(
        data=data, dia_semana="Seg",
        ent1=ent1, sai1=None, ent2=None, sai2=None, ent3=None, sai3=None,
        ex50_min=0, atraso_min=0, btotal_min=btotal_min, exnot_min=0,
    )


def _colab(nome, departamento, admissao, dias):
    total = sum(d.btotal_min or 0 for d in dias)
    return Colaborador(
        nome=nome, funcao="Cargo Teste", admissao=admissao, departamento=departamento,
        dias=dias, total_bruto_min=total,
    )


def test_dept_label_agrupa_csc():
    assert dept_label("CONTROLADORIA") == "Centro de Serviços Compartilhados"
    assert dept_label("Administrativo") == "Centro de Serviços Compartilhados"
    assert dept_label("FINANCEIRO") == "Centro de Serviços Compartilhados"


def test_dept_label_mantem_outros():
    assert dept_label("TECNOLOGIA") == "Tecnologia"
    assert dept_label("HUB FUCAPE") == "Hub Fucape"
    assert dept_label("COMERCIAL") == "Comercial"


def test_saldo_trabalhado_filtra_dias_antes_da_admissao():
    c = _colab(
        "Recem Admitido", "TECNOLOGIA", admissao=datetime.date(2026, 5, 13),
        dias=[
            _dia(datetime.date(2026, 4, 20), btotal_min=-300),  # antes da admissão
            _dia(datetime.date(2026, 5, 15), btotal_min=363),   # depois da admissão (6h03)
        ],
    )
    assert saldo_trabalhado_min(c) == 363


def test_saldo_trabalhado_sem_admissao_usa_total():
    c = _colab(
        "Sem Data", "TECNOLOGIA", admissao=None,
        dias=[_dia(datetime.date(2026, 5, 15), btotal_min=100)],
    )
    assert saldo_trabalhado_min(c) == 100


def test_sem_batida_real_true_quando_nenhum_dia_tem_hora_real():
    c = _colab(
        "Isento", "DIRETORIA", admissao=datetime.date(2020, 1, 1),
        dias=[_dia(datetime.date(2026, 1, d), btotal_min=-480, com_batida=False) for d in range(1, 6)],
    )
    assert sem_batida_real(c) is True


def test_sem_batida_real_false_quando_ha_pelo_menos_um_dia_com_batida():
    c = _colab(
        "Com Ponto", "TECNOLOGIA", admissao=datetime.date(2020, 1, 1),
        dias=[
            _dia(datetime.date(2026, 1, 1), btotal_min=-480, com_batida=False),
            _dia(datetime.date(2026, 1, 2), btotal_min=30, com_batida=True),
        ],
    )
    assert sem_batida_real(c) is False


def test_montar_relatorio_geral_gera_kpis_gauge_ranking_e_deptos():
    positivo = _colab(
        "Credor Grande", "HUB FUCAPE", admissao=datetime.date(2020, 1, 1),
        dias=[_dia(datetime.date(2026, 1, 15), btotal_min=6775)],
    )  # +112h55
    negativo = _colab(
        "Devedor", "TECNOLOGIA", admissao=datetime.date(2020, 1, 1),
        dias=[_dia(datetime.date(2026, 1, 15), btotal_min=-1181)],
    )  # -19h41
    isento = _colab(
        "Config", "DIRETORIA", admissao=datetime.date(2020, 1, 1),
        dias=[_dia(datetime.date(2026, 1, d), btotal_min=-720, com_batida=False) for d in range(1, 31)],
    )  # -360h00, sem nenhuma batida real

    r = montar_relatorio([positivo, negativo, isento], escopo="geral", prefixo_pessoas="deptos/pessoas/")

    assert r["contadores"] == {"total": 3, "elegiveis": 2, "nao_elegiveis": 1}
    assert r["ranking"][0]["nome"] == "Credor Grande"
    assert r["ranking"][0]["classe"] == "p"
    assert r["ranking"][0]["valor_fmt"] == "+112h55"
    assert r["ranking"][0]["pessoa_href"] == "deptos/pessoas/credor-grande.html"
    # +112h55 (6775 min) > escala de 2400 min -> barra travada no teto (50%)
    assert r["ranking"][0]["pct"] == 50.0
    assert r["nota_ranking"] is not None and "Credor" in r["nota_ranking"]
    assert r["ranking"][1]["nome"] == "Devedor"
    assert r["ranking"][1]["classe"] == "n"
    assert r["ranking"][1]["pessoa_href"] == "deptos/pessoas/devedor.html"

    assert r["gauge"]["qtd_passivo"] == 1
    assert r["gauge"]["qtd_receber"] == 1
    assert r["gauge"]["pos_fmt"] == "+112h55"
    assert r["gauge"]["neg_fmt"] == "−19h41"
    assert round(r["gauge"]["neg_pct"] + r["gauge"]["pos_pct"], 4) == 100.0

    assert r["kpis"]["nao_elegiveis"]["valor"] == 1
    assert r["kpis"]["concentracao"]["valor_fmt"] == "+112h55"
    assert r["kpis"]["concentracao"]["pct_fmt"] == "100%"

    assert r["alerta"] is not None and "1 registro" in r["alerta"]

    # "Diretoria" tem só o colaborador "Config" (sem batida real), então some do grid
    # de departamentos — a seção 02 só soma saldo de gente com ponto ativo.
    nomes_deptos = {d["nome"] for d in r["deptos"]}
    assert nomes_deptos == {"Hub Fucape", "Tecnologia"}

    assert r["nao_elegiveis_lista"][0]["nome"] == "Config"
    assert r["nao_elegiveis_lista"][0]["valor_fmt"] == "−360h00"


def test_montar_relatorio_depto_sem_deptos_e_subtitulo_admissao():
    recente = _colab(
        "Recem Chegado", "COORDENAÇÃO DE CURSO", admissao=datetime.date(2026, 5, 13),
        dias=[
            _dia(datetime.date(2026, 4, 20), btotal_min=-18000),
            _dia(datetime.date(2026, 5, 15), btotal_min=363),
        ],
    )
    r = montar_relatorio([recente], escopo="depto")
    assert r["deptos"] is None
    assert "admitido 13/05/2026" in r["ranking"][0]["subtitulo"]
    assert "desde admissão: +6h03" in r["ranking"][0]["subtitulo"]


def test_montar_relatorio_csc_mostra_time_original():
    membro = _colab(
        "Pessoa CSC", "Controladoria", admissao=datetime.date(2020, 1, 1),
        dias=[_dia(datetime.date(2026, 1, 15), btotal_min=100)],
    )
    r = montar_relatorio([membro], escopo="csc")
    assert r["ranking"][0]["subtitulo"] == "Controladoria"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_calculos.py -v`
Expected: FAIL (`is_config`/`Mes` no longer exist / don't match)

- [ ] **Step 3: Rewrite `painel_horas/calculos.py`**

```python
import datetime

from painel_horas.horas import format_horas
from painel_horas.slug import slugify

ESCALA_RANKING_MAX_MIN = 40 * 60

CSC_ORIGENS = {"CONTROLADORIA", "ADMINISTRATIVO", "FINANCEIRO"}
CSC_LABEL = "Centro de Serviços Compartilhados"


def dept_label(departamento: str) -> str:
    if departamento.strip().upper() in CSC_ORIGENS:
        return CSC_LABEL
    return departamento.strip().title()


def saldo_trabalhado_min(colab) -> int:
    if colab.admissao is None:
        return colab.total_bruto_min
    dias = [d for d in colab.dias if d.data >= colab.admissao]
    if not dias:
        return colab.total_bruto_min
    return sum(d.btotal_min or 0 for d in dias)


def _tem_batida_real(dia) -> bool:
    return (
        isinstance(dia.ent1, datetime.timedelta)
        or isinstance(dia.ent2, datetime.timedelta)
        or isinstance(dia.ent3, datetime.timedelta)
    )


def sem_batida_real(colab) -> bool:
    return not any(_tem_batida_real(d) for d in colab.dias)


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


def montar_relatorio(colaboradores: list, escopo: str = "geral", prefixo_pessoas: str = "") -> dict:
    elegiveis = [c for c in colaboradores if not sem_batida_real(c)]
    nao_elegiveis = [c for c in colaboradores if sem_batida_real(c)]

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
            "pessoa_href": f"{prefixo_pessoas}{slugify(c.nome)}.html",
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
            "sub": "Sem nenhuma batida real no período · não indica ausência real",
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
            f"{n_nao} registro{'s' if plural else ''} sem nenhuma batida real no período "
            "(isenção de ponto ou jornada mal configurada). "
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_calculos.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add painel_horas/calculos.py tests/test_calculos.py
git commit -m "feat: classify fora-da-base by zero real punches, drop credito/debito heuristic"
```

---

### Task 4: `calculos.py` — monthly/weekly aggregation, highlights, person context

**Files:**
- Modify: `painel_horas/calculos.py` (append)
- Modify: `tests/test_calculos.py` (append)

**Interfaces:**
- Consumes: `Colaborador`, `Dia` (Task 2); `format_horas`, `dept_label` (already imported in `calculos.py`).
- Produces:
  - `resumo_mensal(colab) -> list[dict]` — each `{"label": str, "total_min": int, "total_fmt": str}`, chronological.
  - `resumo_semanal(colab) -> list[dict]` — each `{"inicio": date, "fim": date, "label": str, "total_min": int, "total_fmt": str}`, chronological, week = Monday–Sunday.
  - `destaques(colab) -> dict` — `{"melhor_dia": {...} | None, "pior_dia": {...} | None, "melhor_mes": {...} | None, "pior_mes": {...} | None, "melhor_semana": {...} | None, "pior_semana": {...} | None}`. `melhor_dia`/`pior_dia` are `{"data_fmt": str, "total_fmt": str, "classe": "tpos"|"tneg"}`; the month/week ones are entries from `resumo_mensal`/`resumo_semanal`.
  - `montar_pessoa(colab) -> dict` — full context for `pessoa.html.j2` (Task 5): `nome, funcao, departamento, admissao_fmt, saldo_total_fmt, saldo_total_min, destaques, mensal, semanal, diario`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_calculos.py` (needs `resumo_mensal, resumo_semanal, destaques, montar_pessoa` added to the existing import line from `painel_horas.calculos`):

```python
def test_resumo_mensal_agrupa_por_ano_mes():
    c = _colab("X", "TECNOLOGIA", admissao=None, dias=[
        _dia(datetime.date(2026, 5, 10), btotal_min=100),
        _dia(datetime.date(2026, 5, 20), btotal_min=50),
        _dia(datetime.date(2026, 6, 1), btotal_min=-30),
    ])
    meses = resumo_mensal(c)
    assert [m["label"] for m in meses] == ["Maio/2026", "Junho/2026"]
    assert meses[0]["total_min"] == 150
    assert meses[1]["total_min"] == -30


def test_resumo_semanal_agrupa_segunda_a_domingo():
    # 11/05/2026 é segunda-feira, 17/05/2026 é domingo da mesma semana
    c = _colab("X", "TECNOLOGIA", admissao=None, dias=[
        _dia(datetime.date(2026, 5, 11), btotal_min=100),
        _dia(datetime.date(2026, 5, 17), btotal_min=50),
        _dia(datetime.date(2026, 5, 18), btotal_min=-10),  # segunda seguinte
    ])
    semanas = resumo_semanal(c)
    assert len(semanas) == 2
    assert semanas[0]["total_min"] == 150
    assert semanas[0]["label"] == "11/05 – 17/05"
    assert semanas[1]["total_min"] == -10


def test_destaques_encontra_melhor_pior_ignora_dias_sem_valor():
    c = _colab("X", "TECNOLOGIA", admissao=None, dias=[
        _dia(datetime.date(2026, 5, 11), btotal_min=200),
        _dia(datetime.date(2026, 5, 12), btotal_min=-100),
        _dia(datetime.date(2026, 5, 13), btotal_min=None, com_batida=False),
    ])
    d = destaques(c)
    assert d["melhor_dia"]["total_fmt"] == "+3h20"
    assert d["pior_dia"]["total_fmt"] == "−1h40"
    assert d["melhor_mes"]["total_min"] == 100
    assert d["melhor_semana"]["total_min"] == 100


def test_montar_pessoa_monta_contexto_completo():
    c = _colab(
        "Fulano de Tal", "TECNOLOGIA", admissao=datetime.date(2020, 1, 1),
        dias=[_dia(datetime.date(2026, 5, 11), btotal_min=100)],
    )
    ctx = montar_pessoa(c)
    assert ctx["nome"] == "Fulano de Tal"
    assert ctx["saldo_total_fmt"] == "+1h40"
    assert len(ctx["diario"]) == 1
    assert ctx["diario"][0]["data_fmt"] == "11/05/2026"
    assert ctx["mensal"][0]["label"] == "Maio/2026"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_calculos.py -v`
Expected: FAIL (`ImportError`/`NameError` — functions don't exist yet)

- [ ] **Step 3: Append to `painel_horas/calculos.py`**

```python
_MESES_PT = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def resumo_mensal(colab) -> list:
    grupos: dict = {}
    for d in colab.dias:
        chave = (d.data.year, d.data.month)
        grupos[chave] = grupos.get(chave, 0) + (d.btotal_min or 0)
    resultado = []
    for (ano, mes), total in sorted(grupos.items()):
        resultado.append({
            "label": f"{_MESES_PT[mes - 1]}/{ano}",
            "total_min": total,
            "total_fmt": format_horas(total),
        })
    return resultado


def resumo_semanal(colab) -> list:
    grupos: dict = {}
    for d in colab.dias:
        inicio_semana = d.data - datetime.timedelta(days=d.data.weekday())
        grupos[inicio_semana] = grupos.get(inicio_semana, 0) + (d.btotal_min or 0)
    resultado = []
    for inicio, total in sorted(grupos.items()):
        fim = inicio + datetime.timedelta(days=6)
        resultado.append({
            "inicio": inicio,
            "fim": fim,
            "label": f"{inicio.strftime('%d/%m')} – {fim.strftime('%d/%m')}",
            "total_min": total,
            "total_fmt": format_horas(total),
        })
    return resultado


def _fmt_dia_destaque(dia):
    if dia is None:
        return None
    return {
        "data_fmt": dia.data.strftime("%d/%m/%Y"),
        "total_fmt": format_horas(dia.btotal_min),
        "classe": "tpos" if dia.btotal_min >= 0 else "tneg",
    }


def destaques(colab) -> dict:
    dias_com_valor = [d for d in colab.dias if d.btotal_min is not None]
    melhor_dia = max(dias_com_valor, key=lambda d: d.btotal_min) if dias_com_valor else None
    pior_dia = min(dias_com_valor, key=lambda d: d.btotal_min) if dias_com_valor else None
    meses = resumo_mensal(colab)
    semanas = resumo_semanal(colab)
    return {
        "melhor_dia": _fmt_dia_destaque(melhor_dia),
        "pior_dia": _fmt_dia_destaque(pior_dia),
        "melhor_mes": max(meses, key=lambda m: m["total_min"]) if meses else None,
        "pior_mes": min(meses, key=lambda m: m["total_min"]) if meses else None,
        "melhor_semana": max(semanas, key=lambda s: s["total_min"]) if semanas else None,
        "pior_semana": min(semanas, key=lambda s: s["total_min"]) if semanas else None,
    }


def _fmt_batida(valor):
    if valor is None:
        return ""
    if isinstance(valor, datetime.timedelta):
        total_min = int(valor.total_seconds() // 60)
        h, m = divmod(total_min, 60)
        return f"{h:02d}:{m:02d}"
    return str(valor)  # código de status (FOLGA, FALTA, etc.)


def montar_pessoa(colab) -> dict:
    dias_ordenados = sorted(colab.dias, key=lambda d: d.data)
    diario = [{
        "data_fmt": dia.data.strftime("%d/%m/%Y"),
        "dia_semana": dia.dia_semana,
        "ent1": _fmt_batida(dia.ent1), "sai1": _fmt_batida(dia.sai1),
        "ent2": _fmt_batida(dia.ent2), "sai2": _fmt_batida(dia.sai2),
        "ent3": _fmt_batida(dia.ent3), "sai3": _fmt_batida(dia.sai3),
        "ex50_fmt": format_horas(dia.ex50_min) if dia.ex50_min else "",
        "atraso_fmt": format_horas(dia.atraso_min) if dia.atraso_min else "",
        "btotal_fmt": format_horas(dia.btotal_min) if dia.btotal_min is not None else "",
        "btotal_classe": ("tpos" if dia.btotal_min >= 0 else "tneg") if dia.btotal_min is not None else "",
        "exnot_fmt": format_horas(dia.exnot_min) if dia.exnot_min else "",
    } for dia in dias_ordenados]

    return {
        "nome": colab.nome,
        "funcao": colab.funcao,
        "departamento": dept_label(colab.departamento),
        "admissao_fmt": colab.admissao.strftime("%d/%m/%Y") if colab.admissao else "",
        "saldo_total_fmt": format_horas(colab.total_bruto_min),
        "saldo_total_min": colab.total_bruto_min,
        "destaques": destaques(colab),
        "mensal": resumo_mensal(colab),
        "semanal": resumo_semanal(colab),
        "diario": diario,
    }
```

Also update the `test_calculos.py` import line at the top of the file to:

```python
from painel_horas.calculos import (
    dept_label, saldo_trabalhado_min, sem_batida_real, montar_relatorio,
    resumo_mensal, resumo_semanal, destaques, montar_pessoa,
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_calculos.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add painel_horas/calculos.py tests/test_calculos.py
git commit -m "feat: add monthly/weekly aggregation and highlights for person page"
```

---

### Task 5: `pessoa.html.j2` template + `render_pessoa`

**Files:**
- Create: `templates/pessoa.html.j2`
- Modify: `painel_horas/template.py`
- Modify: `tests/test_template.py`

**Interfaces:**
- Consumes: `montar_pessoa()` output shape (Task 4); `Colaborador`/`Dia` (Task 2).
- Produces: `render_pessoa(contexto: dict) -> str`.

- [ ] **Step 1: Write the failing tests**

Rewrite the top of `tests/test_template.py` (imports + the `_colab_simples` helper) to:

```python
from painel_horas.calculos import montar_relatorio, montar_pessoa
from painel_horas.parser import Colaborador, Dia
from painel_horas.template import render_pagina, render_pessoa
import datetime


def _colab_simples(nome, departamento, valor_min):
    dia = Dia(
        data=datetime.date(2026, 1, 15), dia_semana="Qui",
        ent1=datetime.timedelta(hours=8), sai1=datetime.timedelta(hours=17),
        ent2=None, sai2=None, ent3=None, sai3=None,
        ex50_min=0, atraso_min=0, btotal_min=valor_min, exnot_min=0,
    )
    return Colaborador(
        nome=nome, funcao="Cargo", admissao=datetime.date(2020, 1, 1), departamento=departamento,
        dias=[dia], total_bruto_min=valor_min,
    )
```

Keep the existing three `test_render_pagina_*` tests unchanged below it (they only use `_colab_simples`, `montar_relatorio`, `render_pagina` — all still work with the new helper). Then append:

```python
def test_render_pessoa_contem_secoes_esperadas():
    c = _colab_simples("Fulano", "TECNOLOGIA", 100)
    html = render_pessoa(montar_pessoa(c))
    assert "<!DOCTYPE html>" in html
    assert "Fulano" in html
    assert "Resumo mensal" in html
    assert "Diário completo" in html
    assert "<script>" in html and "<link" not in html


def test_render_pessoa_escapes_html_special_chars():
    c = _colab_simples("Fulano <script>alert(1)</script> & Cia", "TECNOLOGIA", 100)
    html = render_pessoa(montar_pessoa(c))
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_template.py -v`
Expected: FAIL (`render_pessoa` doesn't exist, `pessoa.html.j2` doesn't exist)

- [ ] **Step 3: Add `render_pessoa` to `painel_horas/template.py`**

```python
import pathlib

from jinja2 import Environment, FileSystemLoader

_DIR_TEMPLATES = pathlib.Path(__file__).resolve().parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_DIR_TEMPLATES)),
    autoescape=True,
)


def render_pagina(contexto: dict) -> str:
    template = _env.get_template("painel.html.j2")
    return template.render(**contexto)


def render_pessoa(contexto: dict) -> str:
    template = _env.get_template("pessoa.html.j2")
    return template.render(**contexto)
```

- [ ] **Step 4: Create `templates/pessoa.html.j2`**

```html
<!DOCTYPE html><html lang="pt-BR"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{ nome }} · Cartão Ponto · Fucape</title>
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
.destaques{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px}
.dcard{background:var(--panel);border:1px solid var(--line);border-radius:8px;padding:14px}
.d-val{font-size:18px;font-weight:800}
.d-lab{font-size:11.5px;color:var(--mut);margin-top:4px}
.d-sub{font-size:11px;color:var(--mut);margin-top:6px}
.tpos{color:var(--pos)}
.tneg{color:var(--neg)}
.tabs{display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap}
.tab{background:var(--panel);border:1px solid var(--line);color:var(--mut);font-size:12px;padding:8px 14px;border-radius:6px;cursor:pointer}
.tab.on{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.painel-tab{display:none}
.painel-tab.on{display:block}
.tbl{width:100%;border-collapse:collapse;font-size:12px}
.tbl th{text-align:left;color:var(--mut);font-weight:600;font-size:11px;text-transform:uppercase;padding:6px 8px;border-bottom:1px solid var(--line)}
.tbl td{padding:8px;border-bottom:1px solid var(--line)}
.tbl .rt{text-align:right}
.tbl .mono{font-variant-numeric:tabular-nums}
footer{font-size:11px;color:var(--mut);border-top:1px solid var(--line);padding-top:16px;margin-top:8px}
</style>
</head><body>
<div class="wrap">

<header>
  <div>
    <div class="eyebrow">Fucape Business School · Cartão Ponto Secullum</div>
    <h1>{{ nome }} <span>/ Controle de ponto</span></h1>
  </div>
  <div class="meta">
    {{ funcao }} · {{ departamento }}<br>
    {% if admissao_fmt %}Admitido <b>{{ admissao_fmt }}</b><br>{% endif %}
    Saldo total <b class="{{ 'tpos' if saldo_total_min >= 0 else 'tneg' }}">{{ saldo_total_fmt }}</b>
  </div>
</header>

<div class="destaques">
  <div class="dcard">
    <div class="d-val {{ destaques.melhor_dia.classe if destaques.melhor_dia else '' }}">{{ destaques.melhor_dia.total_fmt if destaques.melhor_dia else '—' }}</div>
    <div class="d-lab">Melhor dia</div>
    <div class="d-sub">{{ destaques.melhor_dia.data_fmt if destaques.melhor_dia else '' }}</div>
  </div>
  <div class="dcard">
    <div class="d-val {{ destaques.pior_dia.classe if destaques.pior_dia else '' }}">{{ destaques.pior_dia.total_fmt if destaques.pior_dia else '—' }}</div>
    <div class="d-lab">Pior dia</div>
    <div class="d-sub">{{ destaques.pior_dia.data_fmt if destaques.pior_dia else '' }}</div>
  </div>
  <div class="dcard">
    <div class="d-val">{{ saldo_total_fmt }}</div>
    <div class="d-lab">Saldo total do período</div>
    <div class="d-sub">&nbsp;</div>
  </div>
  <div class="dcard">
    <div class="d-val {{ 'tpos' if destaques.melhor_semana and destaques.melhor_semana.total_min >= 0 else 'tneg' if destaques.melhor_semana else '' }}">{{ destaques.melhor_semana.total_fmt if destaques.melhor_semana else '—' }}</div>
    <div class="d-lab">Melhor semana</div>
    <div class="d-sub">{{ destaques.melhor_semana.label if destaques.melhor_semana else '' }}</div>
  </div>
  <div class="dcard">
    <div class="d-val {{ 'tpos' if destaques.pior_semana and destaques.pior_semana.total_min >= 0 else 'tneg' if destaques.pior_semana else '' }}">{{ destaques.pior_semana.total_fmt if destaques.pior_semana else '—' }}</div>
    <div class="d-lab">Pior semana</div>
    <div class="d-sub">{{ destaques.pior_semana.label if destaques.pior_semana else '' }}</div>
  </div>
  <div class="dcard">
    <div class="d-val {{ 'tpos' if destaques.melhor_mes and destaques.melhor_mes.total_min >= 0 else 'tneg' if destaques.melhor_mes else '' }}">{{ destaques.melhor_mes.total_fmt if destaques.melhor_mes else '—' }}</div>
    <div class="d-lab">Melhor mês</div>
    <div class="d-sub">{{ destaques.melhor_mes.label if destaques.melhor_mes else '' }}</div>
  </div>
</div>

<div class="tabs">
  <button class="tab on" data-tab="mensal">Resumo mensal</button>
  <button class="tab" data-tab="semanal">Semanal</button>
  <button class="tab" data-tab="diario">Diário completo</button>
</div>

<div class="painel-tab on" id="tab-mensal">
  <table class="tbl">
    <thead><tr><th>Mês</th><th class="rt">Saldo</th></tr></thead>
    <tbody>
      {% for m in mensal %}
      <tr><td>{{ m.label }}</td><td class="rt mono {{ 'tpos' if m.total_min >= 0 else 'tneg' }}">{{ m.total_fmt }}</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>

<div class="painel-tab" id="tab-semanal">
  <table class="tbl">
    <thead><tr><th>Semana</th><th class="rt">Saldo</th></tr></thead>
    <tbody>
      {% for s in semanal %}
      <tr><td>{{ s.label }}</td><td class="rt mono {{ 'tpos' if s.total_min >= 0 else 'tneg' }}">{{ s.total_fmt }}</td></tr>
      {% endfor %}
    </tbody>
  </table>
</div>

<div class="painel-tab" id="tab-diario">
  <table class="tbl">
    <thead><tr><th>Data</th><th>Ent.1</th><th>Saí.1</th><th>Ent.2</th><th>Saí.2</th><th>Ent.3</th><th>Saí.3</th><th class="rt">Ex50%</th><th class="rt">Atraso</th><th class="rt">Saldo</th><th class="rt">Ex.Not</th></tr></thead>
    <tbody>
      {% for d in diario %}
      <tr>
        <td>{{ d.data_fmt }} <span style="color:var(--mut)">{{ d.dia_semana }}</span></td>
        <td class="mono">{{ d.ent1 }}</td><td class="mono">{{ d.sai1 }}</td>
        <td class="mono">{{ d.ent2 }}</td><td class="mono">{{ d.sai2 }}</td>
        <td class="mono">{{ d.ent3 }}</td><td class="mono">{{ d.sai3 }}</td>
        <td class="rt mono">{{ d.ex50_fmt }}</td>
        <td class="rt mono">{{ d.atraso_fmt }}</td>
        <td class="rt mono {{ d.btotal_classe }}">{{ d.btotal_fmt }}</td>
        <td class="rt mono">{{ d.exnot_fmt }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>

<footer>
  <b>Metodologia.</b> Fonte: Cartão Ponto Secullum Ponto Web. Saldo diário (BTotal) somado dia a dia; os resumos mensal e semanal são agregações do mesmo valor.<br>
  <b>Limite de leitura.</b> Cartão ponto mede presença registrada, não produtividade nem entrega.
</footer>

</div>
<script>
document.querySelectorAll('.tabs .tab').forEach(function(btn){
  btn.addEventListener('click', function(){
    document.querySelectorAll('.tabs .tab').forEach(function(b){ b.classList.remove('on'); });
    btn.classList.add('on');
    document.querySelectorAll('.painel-tab').forEach(function(p){ p.classList.remove('on'); });
    document.getElementById('tab-' + btn.dataset.tab).classList.add('on');
  });
});
</script>
</body></html>
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_template.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add painel_horas/template.py templates/pessoa.html.j2 tests/test_template.py
git commit -m "feat: add person detail page template (highlights + monthly/weekly/daily tabs)"
```

---

### Task 6: Link employee names to their person page in `painel.html.j2`

**Files:**
- Modify: `templates/painel.html.j2`
- Modify: `tests/test_template.py`

**Interfaces:**
- Consumes: `ranking[i]["pessoa_href"]` from Task 3's `montar_relatorio`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_template.py`:

```python
def test_render_pagina_linka_nome_para_pagina_de_pessoa():
    r = montar_relatorio([_colab_simples("Fulano", "TECNOLOGIA", 100)], escopo="geral", prefixo_pessoas="deptos/pessoas/")
    html = render_pagina({
        "escopo_titulo": "Painel do CEO", "periodo_texto": "01/01/2026 → 09/07/2026",
        "data_emissao": "10/07/2026", "mostrar_deptos": True, "r": r,
    })
    assert 'href="deptos/pessoas/fulano.html"' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_template.py::test_render_pagina_linka_nome_para_pagina_de_pessoa -v`
Expected: FAIL (name isn't a link yet)

- [ ] **Step 3: Edit `templates/painel.html.j2`**

Change the ranking row markup (currently):

```html
      <div class="br-name">{{ pessoa.nome }}<small>{{ pessoa.subtitulo }}</small></div>
```

to:

```html
      <div class="br-name"><a href="{{ pessoa.pessoa_href }}">{{ pessoa.nome }}</a><small>{{ pessoa.subtitulo }}</small></div>
```

Add a CSS rule next to the existing `.d-name a{...}` rule:

```css
.br-name a{color:inherit;text-decoration:none}
```

Also update the two hardcoded "Extrato"-era copy lines so they don't lie about the new data source. Change the eyebrow:

```html
    <div class="eyebrow">Fucape Business School · Extrato Secullum</div>
```

to:

```html
    <div class="eyebrow">Fucape Business School · Cartão Ponto Secullum</div>
```

And change the KPI "não elegíveis" card label + footer methodology text:

```html
  <div class="kpi b"><div class="k-val" style="color:var(--blue)">{{ r.kpis.nao_elegiveis.valor }}</div><div class="k-lab">Registros não elegíveis<br>débito padrão &#8805;300h</div><div class="k-sub">{{ r.kpis.nao_elegiveis.sub }}</div></div>
```

to:

```html
  <div class="kpi b"><div class="k-val" style="color:var(--blue)">{{ r.kpis.nao_elegiveis.valor }}</div><div class="k-lab">Registros não elegíveis<br>sem batida real no período</div><div class="k-sub">{{ r.kpis.nao_elegiveis.sub }}</div></div>
```

and:

```html
  <b>Metodologia.</b> Fonte: Extrato do Banco de Horas Secullum Ponto Web, período {{ periodo_texto }}.
  Saldos somados a partir do total mensal de cada colaborador. "Elegível" = possui batidas reais no período.
  "Não elegível" = débito padrão &#8805; 300h sem crédito, indicando isenção ou jornada mal configurada.<br>
```

to:

```html
  <b>Metodologia.</b> Fonte: Cartão Ponto Secullum Ponto Web, período {{ periodo_texto }}.
  Saldos somados a partir do saldo diário (BTotal) de cada colaborador. "Elegível" = tem ao menos uma batida real no período.
  "Não elegível" = nenhuma batida real no período, indicando isenção de ponto ou jornada mal configurada.<br>
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_template.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Commit**

```bash
git add templates/painel.html.j2 tests/test_template.py
git commit -m "feat: link ranking names to person page, update copy for cartaoponto source"
```

---

### Task 7: `atualizar_painel.py` — orchestrate person page generation/cleanup

**Files:**
- Modify: `atualizar_painel.py`
- Modify: `tests/test_atualizar_painel.py`

**Interfaces:**
- Consumes: `ler_colaboradores` (Task 2), `montar_relatorio`/`sem_batida_real`/`montar_pessoa`/`CSC_LABEL`/`dept_label` (Task 3/4), `render_pagina`/`render_pessoa` (Task 5), `slugify` (unchanged).
- Produces: `gerar_painel(caminho_xlsx, pasta_saida) -> dict` (same return shape as before), now also writing `pasta_saida/deptos/pessoas/<slug>.html` and cleaning that folder each run.

- [ ] **Step 1: Rewrite `tests/test_atualizar_painel.py`**

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


def _dia_com_batida(data_str, btotal_str):
    return (data_str, "Qui", datetime.timedelta(hours=8), datetime.timedelta(hours=17),
            None, None, None, None, None, None, btotal_str, None)


def _dia_sem_batida(data_str, btotal_str):
    return (data_str, "Qui", "FALTA", "FALTA", None, None, None, None, None, None, btotal_str, None)


def test_gerar_painel_cria_index_deptos_e_paginas_de_pessoa(tmp_path, workbook_path):
    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("01/06/2026", "+05:00")],
        },
        {
            "nome": "PESSOA CONTROLADORIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "CONTROLADORIA",
            "dias": [_dia_com_batida("01/06/2026", "-02:00")],
        },
        {
            "nome": "PESSOA ADMINISTRATIVO", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "ADMINISTRATIVO",
            "dias": [_dia_com_batida("01/06/2026", "+01:00")],
        },
        {
            "nome": "PESSOA ISENTA", "funcao": "DIRETOR", "admissao": "01/01/2020",
            "departamento": "DIRETORIA",
            "dias": [_dia_sem_batida("01/06/2026", "-08:00")],
        },
    ])
    pasta_saida = tmp_path / "painel"

    resumo = gerar_painel(caminho, pasta_saida)

    assert resumo["colaboradores"] == 4
    assert resumo["departamentos"] == 3  # Tecnologia + CSC (Controladoria+Administrativo) + Diretoria
    assert (pasta_saida / "index.html").exists()
    assert (pasta_saida / "deptos" / "tecnologia.html").exists()
    assert (pasta_saida / "deptos" / "centro-servicos-compartilhados.html").exists()
    assert not (pasta_saida / "deptos" / "controladoria.html").exists()

    # páginas de pessoa: uma por colaborador elegível, nenhuma pro isento
    assert (pasta_saida / "deptos" / "pessoas" / "pessoa-tecnologia.html").exists()
    assert (pasta_saida / "deptos" / "pessoas" / "pessoa-controladoria.html").exists()
    assert (pasta_saida / "deptos" / "pessoas" / "pessoa-administrativo.html").exists()
    assert not (pasta_saida / "deptos" / "pessoas" / "pessoa-isenta.html").exists()

    conteudo_dept = (pasta_saida / "deptos" / "tecnologia.html").read_text(encoding="utf-8")
    assert 'href="pessoas/pessoa-tecnologia.html"' in conteudo_dept

    conteudo_index = (pasta_saida / "index.html").read_text(encoding="utf-8")
    assert 'href="deptos/pessoas/pessoa-tecnologia.html"' in conteudo_index


def test_gerar_painel_remove_paginas_obsoletas_de_departamento_e_pessoa(tmp_path, workbook_path):
    pasta_saida = tmp_path / "painel"

    caminho_v1 = workbook_path([
        {
            "nome": "PESSOA MARKETING", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "MARKETING",
            "dias": [_dia_com_batida("01/06/2026", "+01:00")],
        },
    ])
    gerar_painel(caminho_v1, pasta_saida)
    assert (pasta_saida / "deptos" / "marketing.html").exists()
    assert (pasta_saida / "deptos" / "pessoas" / "pessoa-marketing.html").exists()

    caminho_v2 = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("01/06/2026", "+01:00")],
        },
    ])
    gerar_painel(caminho_v2, pasta_saida)

    # arquivos obsoletos da rodada anterior não podem continuar no ar com dado desatualizado
    assert not (pasta_saida / "deptos" / "marketing.html").exists()
    assert not (pasta_saida / "deptos" / "pessoas" / "pessoa-marketing.html").exists()
    assert (pasta_saida / "deptos" / "tecnologia.html").exists()
    assert (pasta_saida / "deptos" / "pessoas" / "pessoa-tecnologia.html").exists()


def test_main_sem_xlsx_nao_gera_nada_e_avisa(tmp_path, monkeypatch, capsys):
    import atualizar_painel
    monkeypatch.setattr(atualizar_painel, "__file__", str(tmp_path / "atualizar_painel.py"))
    (tmp_path / "extratos").mkdir()

    atualizar_painel.main()

    saida = capsys.readouterr()
    assert "erro" in saida.out
    assert not (tmp_path / "painel").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_atualizar_painel.py -v`
Expected: FAIL (`_periodo_texto` reads `c.meses` which no longer exists; no `pessoas/` folder generated)

- [ ] **Step 3: Rewrite `atualizar_painel.py`**

```python
import webbrowser
from datetime import date
from pathlib import Path

from painel_horas.calculos import CSC_LABEL, dept_label, montar_relatorio, montar_pessoa, sem_batida_real
from painel_horas.parser import ler_colaboradores
from painel_horas.slug import slugify
from painel_horas.template import render_pagina, render_pessoa


def encontrar_xlsx_mais_recente(pasta: Path) -> Path | None:
    arquivos = list(pasta.glob("*.xlsx"))
    if not arquivos:
        return None
    return max(arquivos, key=lambda p: p.stat().st_mtime)


def _periodo_texto(colaboradores) -> str:
    todas_datas = [d.data for c in colaboradores for d in c.dias]
    if not todas_datas:
        return ""
    return f"{min(todas_datas).strftime('%d/%m/%Y')} → {max(todas_datas).strftime('%d/%m/%Y')}"


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
    for arquivo_antigo in pasta_deptos.glob("*.html"):
        arquivo_antigo.unlink()
    pasta_pessoas = pasta_deptos / "pessoas"
    pasta_pessoas.mkdir(exist_ok=True)
    for arquivo_antigo in pasta_pessoas.glob("*.html"):
        arquivo_antigo.unlink()

    relatorio_geral = montar_relatorio(colaboradores, escopo="geral", prefixo_pessoas="deptos/pessoas/")
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
        relatorio = montar_relatorio(membros, escopo=escopo, prefixo_pessoas="pessoas/")
        html = render_pagina({
            "escopo_titulo": f"Painel {label}",
            "periodo_texto": periodo_texto,
            "data_emissao": data_emissao,
            "mostrar_deptos": False,
            "r": relatorio,
        })
        (pasta_deptos / f"{slugify(label)}.html").write_text(html, encoding="utf-8")

        for c in membros:
            if sem_batida_real(c):
                continue
            html_pessoa = render_pessoa(montar_pessoa(c))
            (pasta_pessoas / f"{slugify(c.nome)}.html").write_text(html_pessoa, encoding="utf-8")

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_atualizar_painel.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add atualizar_painel.py tests/test_atualizar_painel.py
git commit -m "feat: generate and clean up person pages per department in gerar_painel"
```

---

### Task 8: Full suite check

**Files:** none (verification only)

- [ ] **Step 1: Run the entire test suite**

Run: `python -m pytest -v`
Expected: all tests PASS, no leftover references to `Mes`, `is_config`, or `NOME:` anywhere (sanity check — none of the earlier tasks should have left dead imports).

- [ ] **Step 2: Manually generate the real painel once**

Copy `cartaoponto.xlsx` into `extratos/` (create the folder if it doesn't exist) and run:

Run: `python atualizar_painel.py`
Expected: console prints `Painel atualizado: 42 colaboradores, N departamentos` and opens `painel/index.html` in the browser. Click an employee name in the ranking and confirm it opens their `deptos/pessoas/<slug>.html` page with highlight cards and the three tabs working.

- [ ] **Step 3: Commit if step 2 required any fixup**

Only if step 2 surfaced a bug — fix it, re-run step 1, then:

```bash
git add -A
git commit -m "fix: <describe the fix>"
```
