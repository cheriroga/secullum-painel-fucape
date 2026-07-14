import datetime

import pytest

from webapp.pipeline import processar_upload


def _dia_com_batida(data_str, btotal_str):
    return (data_str, "Qui", datetime.timedelta(hours=8), datetime.timedelta(hours=17),
            None, None, None, None, None, None, btotal_str, None)


def test_processar_upload_gera_painel_em_pasta_do_periodo(tmp_path, workbook_path):
    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("15/06/2026", "+05:00")],
        },
    ])
    pasta_base = tmp_path / "painel_web"

    resultado = processar_upload(caminho, pasta_base)

    assert resultado["periodo"] == "2026-06"
    assert resultado["periodo_extenso"] == "Junho/2026"
    assert resultado["pasta"] == pasta_base / "2026-06"
    assert resultado["colaboradores"] == 1
    assert resultado["departamentos_labels"] == ["Tecnologia"]
    assert (pasta_base / "2026-06" / "index.html").exists()


def test_processar_upload_sem_colaboradores_reconheciveis_leva_a_erro(tmp_path, workbook_path):
    caminho = workbook_path([])
    pasta_base = tmp_path / "painel_web"

    with pytest.raises(ValueError):
        processar_upload(caminho, pasta_base)
