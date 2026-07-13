import datetime

import pytest

from painel_horas.parser import Colaborador, Dia
from webapp.periodo import periodo_slug


def _dia(data_str):
    ano, mes, dia = map(int, data_str.split("-"))
    return Dia(
        data=datetime.date(ano, mes, dia), dia_semana="Qui",
        ent1=None, sai1=None, ent2=None, sai2=None, ent3=None, sai3=None,
        ex50_min=0, atraso_min=0, btotal_min=0, exnot_min=0,
    )


def test_periodo_slug_usa_ano_mes_da_data_mais_antiga():
    colaboradores = [
        Colaborador(
            nome="A", funcao="X", admissao=None, departamento="TI",
            dias=[_dia("2026-06-15"), _dia("2026-06-30")],
        ),
        Colaborador(
            nome="B", funcao="X", admissao=None, departamento="TI",
            dias=[_dia("2026-06-01")],
        ),
    ]
    assert periodo_slug(colaboradores) == "2026-06"


def test_periodo_slug_sem_dias_registrados_leva_a_erro():
    colaboradores = [Colaborador(nome="A", funcao="X", admissao=None, departamento="TI", dias=[])]
    with pytest.raises(ValueError):
        periodo_slug(colaboradores)
