from painel_horas.parser import Colaborador


def periodo_slug(colaboradores: list[Colaborador]) -> str:
    """Retorna o período (ano-mês) da data mais antiga encontrada entre
    todos os dias de todos os colaboradores, no formato "AAAA-MM"."""
    todas_datas = [dia.data for colaborador in colaboradores for dia in colaborador.dias]
    if not todas_datas:
        raise ValueError("Arquivo sem dias registrados — não é possível determinar o período.")
    data_mais_antiga = min(todas_datas)
    return data_mais_antiga.strftime("%Y-%m")
