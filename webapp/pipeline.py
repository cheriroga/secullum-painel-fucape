from pathlib import Path

from atualizar_painel import gerar_painel
from painel_horas.calculos import dept_label
from painel_horas.codigos import caminho_dicionario
from painel_horas.parser import ler_colaboradores
from webapp.periodo import periodo_extenso, periodo_slug


def processar_upload(caminho_xlsx: Path, pasta_base: Path) -> dict:
    colaboradores = ler_colaboradores(caminho_xlsx)
    if not colaboradores:
        raise ValueError("Nenhum colaborador reconhecido no arquivo enviado.")

    periodo = periodo_slug(colaboradores)
    pasta_periodo = pasta_base / periodo
    # Dicionário de códigos fica ao lado de pasta_base (não dentro dela), pra não
    # ir pro deploy; é estável entre períodos, então o mesmo depto mantém a URL.
    resumo = gerar_painel(caminho_xlsx, pasta_periodo, caminho_dicionario(pasta_base.parent))
    departamentos_labels = sorted({dept_label(c.departamento) for c in colaboradores})

    return {
        "periodo": periodo,
        "periodo_extenso": periodo_extenso(colaboradores),
        "pasta": pasta_periodo,
        "departamentos_labels": departamentos_labels,
        **resumo,
    }
