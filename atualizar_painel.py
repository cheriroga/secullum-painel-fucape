import shutil
import webbrowser
from datetime import date
from pathlib import Path

from painel_horas.calculos import CSC_LABEL, dept_label, montar_relatorio, montar_pessoa, sem_batida_real
from painel_horas.codigos import LABEL_CEO, MapaCodigos, caminho_dicionario
from painel_horas.parser import ler_colaboradores
from painel_horas.slug import slugify
from painel_horas.template import render_pagina, render_pessoa

# Página neutra na raiz do período: quem truncar a URL de um painel até
# <periodo>/ cai aqui, sem nenhum dado. Impede que um gestor chegue no painel
# do CEO (ou de outro depto) subindo o caminho.
_STUB_RAIZ = (
    '<!doctype html><html lang="pt-BR"><head><meta charset="UTF-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
    "<title>Fucape</title></head>"
    '<body style="margin:0;background:#0b0f14;color:#8a97a6;font:14px -apple-system,Segoe UI,Roboto,sans-serif">'
    '<div style="max-width:480px;margin:15vh auto;padding:0 24px;text-align:center">'
    "<p>Nada por aqui. Use o link que você recebeu por e-mail.</p>"
    "</div></body></html>"
)


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


def gerar_painel(caminho_xlsx: Path, pasta_saida: Path, caminho_codigos: Path | None = None) -> dict:
    colaboradores = ler_colaboradores(caminho_xlsx)
    periodo_texto = _periodo_texto(colaboradores)
    data_emissao = date.today().strftime("%d/%m/%Y")

    # Com dicionário de códigos, cada arquivo de departamento E de pessoa é
    # nomeado por um código opaco (ex.: k7m2a9.html) em vez do slug legível —
    # assim ninguém adivinha a URL de outro depto nem de outra pessoa pelo nome.
    # Sem dicionário (uso legado), cai no slug.
    if caminho_codigos is not None:
        mapa_codigos = MapaCodigos.carregar(caminho_codigos)
        slug = mapa_codigos.codigo
    else:
        mapa_codigos = None
        slug = slugify

    # Cada escopo (CEO e cada depto) vira uma pasta própria de código opaco com
    # index.html dentro; pessoas ficam numa pasta compartilhada. A raiz do
    # período só tem o stub neutro. Assim, subir/truncar a URL nunca leva de um
    # escopo pro outro. Regenera do zero pra não deixar pasta obsoleta no ar.
    pasta_saida.mkdir(parents=True, exist_ok=True)
    for item in pasta_saida.iterdir():
        shutil.rmtree(item) if item.is_dir() else item.unlink()

    (pasta_saida / "index.html").write_text(_STUB_RAIZ, encoding="utf-8")

    pasta_pessoas = pasta_saida / "pessoas"
    pasta_pessoas.mkdir()

    ceo_slug = slug(LABEL_CEO)
    relatorio_geral = montar_relatorio(colaboradores, escopo="geral", prefixo_pessoas="../pessoas/", codigo=slug)
    html_geral = render_pagina({
        "escopo_titulo": "Painel do CEO",
        "periodo_texto": periodo_texto,
        "data_emissao": data_emissao,
        "mostrar_deptos": True,
        "r": relatorio_geral,
    })
    pasta_ceo = pasta_saida / ceo_slug
    pasta_ceo.mkdir()
    (pasta_ceo / "index.html").write_text(html_geral, encoding="utf-8")

    grupos = _agrupar_por_departamento(colaboradores)
    for label, membros in grupos.items():
        escopo = "csc" if label == CSC_LABEL else "depto"
        relatorio = montar_relatorio(membros, escopo=escopo, prefixo_pessoas="../pessoas/", codigo=slug)
        html = render_pagina({
            "escopo_titulo": f"Painel {label}",
            "periodo_texto": periodo_texto,
            "data_emissao": data_emissao,
            "mostrar_deptos": False,
            "r": relatorio,
        })
        pasta_depto = pasta_saida / slug(label)
        pasta_depto.mkdir()
        (pasta_depto / "index.html").write_text(html, encoding="utf-8")

        for c in membros:
            if sem_batida_real(c):
                continue
            html_pessoa = render_pessoa(montar_pessoa(c, periodo_texto))
            (pasta_pessoas / f"{slug(c.nome)}.html").write_text(html_pessoa, encoding="utf-8")

    if mapa_codigos is not None:
        mapa_codigos.salvar()

    return {
        "colaboradores": len(colaboradores),
        "departamentos": len(grupos),
        "elegiveis": relatorio_geral["contadores"]["elegiveis"],
        "nao_elegiveis": relatorio_geral["contadores"]["nao_elegiveis"],
        "ceo_slug": ceo_slug,
    }


def main() -> None:
    raiz = Path(__file__).resolve().parent
    pasta_extratos = raiz / "extratos"
    pasta_saida = raiz / "painel"

    xlsx = encontrar_xlsx_mais_recente(pasta_extratos)
    if xlsx is None:
        print(f"[erro] nenhum arquivo .xlsx encontrado em {pasta_extratos} — nada foi gerado.")
        return

    resumo = gerar_painel(xlsx, pasta_saida, caminho_dicionario(raiz))
    print(f"Painel atualizado: {resumo['colaboradores']} colaboradores, {resumo['departamentos']} departamentos")
    print(f"  {resumo['elegiveis']} elegíveis · {resumo['nao_elegiveis']} fora da base")

    webbrowser.open((pasta_saida / resumo["ceo_slug"] / "index.html").resolve().as_uri())


if __name__ == "__main__":
    main()
