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
            html_pessoa = render_pessoa(montar_pessoa(c, periodo_texto))
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
