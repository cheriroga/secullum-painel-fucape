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
