import datetime
from painel_horas.parser import ler_colaboradores


def test_ler_colaboradores_bloco_completo(workbook_path):
    caminho = workbook_path([
        {
            "nome": "ANA CARLA CRISTOVAO DA SILVA",
            "funcao": "ASSISTENTE DE COORDENAÇÃO",
            "admissao": "13/05/2026",
            "departamento": "COORDENAÇÃO DE CURSO",
            "dias": [
                ("11/05/2026", "Seg", datetime.timedelta(hours=8), datetime.timedelta(hours=12),
                 datetime.timedelta(hours=13), datetime.timedelta(hours=18), None, None,
                 datetime.timedelta(0), datetime.timedelta(0), "+00:12", datetime.timedelta(0)),
                ("12/05/2026", "Ter", "FALTA", "FALTA", None, None, None, None,
                 None, None, None, None),
            ],
        },
    ])

    colaboradores = ler_colaboradores(caminho)

    assert len(colaboradores) == 1
    c = colaboradores[0]
    assert c.nome == "ANA CARLA CRISTOVAO DA SILVA"
    assert c.funcao == "ASSISTENTE DE COORDENAÇÃO"
    assert c.admissao == datetime.date(2026, 5, 13)
    assert c.departamento == "COORDENAÇÃO DE CURSO"
    assert len(c.dias) == 2
    assert c.dias[0].data == datetime.date(2026, 5, 11)
    assert c.dias[0].dia_semana == "Seg"
    assert c.dias[0].btotal_min == 12
    assert c.dias[1].data == datetime.date(2026, 5, 12)
    assert c.dias[1].btotal_min is None
    assert c.dias[1].ent1 == "FALTA"
    assert c.total_bruto_min == 12


def test_ler_colaboradores_bloco_incompleto_usa_fallback(workbook_path, capsys):
    caminho = workbook_path([
        {
            "nome": "FULANO SEM DADOS",
            "funcao": "ESTAGIARIO",
            "admissao": None,
            "departamento": None,
            "dias": [
                ("01/06/2026", "Seg", datetime.timedelta(hours=8), datetime.timedelta(hours=17),
                 None, None, None, None, None, None, "+00:00", None),
            ],
        },
    ])

    colaboradores = ler_colaboradores(caminho)

    assert len(colaboradores) == 1
    c = colaboradores[0]
    assert c.admissao is None
    assert c.departamento == "Sem Departamento"
    saida = capsys.readouterr()
    assert "FULANO SEM DADOS" in saida.out


def test_ler_colaboradores_multiplos_blocos(workbook_path):
    caminho = workbook_path([
        {
            "nome": "PESSOA UM", "funcao": "CARGO A", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [("01/06/2026", "Seg", datetime.timedelta(hours=8), datetime.timedelta(hours=17),
                      None, None, None, None, None, None, "+01:00", None)],
        },
        {
            "nome": "PESSOA DOIS", "funcao": "CARGO B", "admissao": "01/02/2020",
            "departamento": "BIBLIOTECA",
            "dias": [("01/06/2026", "Seg", datetime.timedelta(hours=8), datetime.timedelta(hours=17),
                      None, None, None, None, None, None, "-01:00", None)],
        },
    ])

    colaboradores = ler_colaboradores(caminho)

    assert [c.nome for c in colaboradores] == ["PESSOA UM", "PESSOA DOIS"]
    assert colaboradores[0].departamento == "TECNOLOGIA"
    assert colaboradores[1].departamento == "BIBLIOTECA"
