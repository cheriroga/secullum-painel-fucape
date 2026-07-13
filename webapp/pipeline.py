from pathlib import Path

from atualizar_painel import gerar_painel
from painel_horas.calculos import dept_label
from painel_horas.parser import ler_colaboradores
from webapp.periodo import periodo_slug


def processar_upload(caminho_xlsx: Path, pasta_base: Path) -> dict:
    colaboradores = ler_colaboradores(caminho_xlsx)
    if not colaboradores:
        raise ValueError("Nenhum colaborador reconhecido no arquivo enviado.")

    periodo = periodo_slug(colaboradores)
    pasta_periodo = pasta_base / periodo
    resumo = gerar_painel(caminho_xlsx, pasta_periodo)
    departamentos_labels = sorted({dept_label(c.departamento) for c in colaboradores})

    return {
        "periodo": periodo,
        "pasta": pasta_periodo,
        "departamentos_labels": departamentos_labels,
        **resumo,
    }
