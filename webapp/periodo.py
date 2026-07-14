from painel_horas.parser import Colaborador

_MESES_PT = (
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
)


def _todas_datas(colaboradores: list[Colaborador]):
    todas_datas = [dia.data for colaborador in colaboradores for dia in colaborador.dias]
    if not todas_datas:
        raise ValueError("Arquivo sem dias registrados — não é possível determinar o período.")
    return todas_datas


def periodo_slug(colaboradores: list[Colaborador]) -> str:
    """Retorna o período (ano-mês) da data mais antiga encontrada entre
    todos os dias de todos os colaboradores, no formato "AAAA-MM"."""
    data_mais_antiga = min(_todas_datas(colaboradores))
    return data_mais_antiga.strftime("%Y-%m")


def periodo_extenso(colaboradores: list[Colaborador]) -> str:
    """Retorna o período coberto por extenso, ex.: "Junho/2026", ou
    "Janeiro/2026 a Junho/2026" se os dias cobrirem mais de um mês."""
    todas_datas = _todas_datas(colaboradores)
    data_min, data_max = min(todas_datas), max(todas_datas)
    inicio = f"{_MESES_PT[data_min.month - 1]}/{data_min.year}"
    if (data_min.year, data_min.month) == (data_max.year, data_max.month):
        return inicio
    fim = f"{_MESES_PT[data_max.month - 1]}/{data_max.year}"
    return f"{inicio} a {fim}"
