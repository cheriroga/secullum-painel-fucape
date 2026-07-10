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
