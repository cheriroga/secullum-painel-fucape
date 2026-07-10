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
