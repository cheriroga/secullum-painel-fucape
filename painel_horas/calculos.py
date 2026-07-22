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


def montar_relatorio(colaboradores: list, escopo: str = "geral", prefixo_pessoas: str = "", codigo=None) -> dict:
    # codigo: função rótulo/nome -> slug do arquivo (depto e pessoa). Default
    # slugify (nome legível); a geração real passa o código opaco pra ninguém
    # adivinhar a URL de outro departamento nem de outra pessoa.
    resolver_slug = codigo or slugify
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
            "pessoa_href": f"{prefixo_pessoas}{resolver_slug(c.nome)}.html",
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
                "slug": resolver_slug(label),
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


def montar_pessoa(colab, periodo_texto: str = "") -> dict:
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
        "periodo_texto": periodo_texto,
        "destaques": destaques(colab),
        "mensal": resumo_mensal(colab),
        "semanal": resumo_semanal(colab),
        "diario": diario,
    }
