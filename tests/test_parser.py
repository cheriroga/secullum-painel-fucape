import datetime
from painel_horas.parser import ler_colaboradores


def test_ler_colaboradores_bloco_completo(workbook_path):
    caminho = workbook_path([
        {
            "nome": "ANA CARLA CRISTOVAO DA SILVA",
            "funcao": "ASSISTENTE DE COORDENAÇÃO",
            "admissao": "13/05/2026",
            "departamento": "COORDENAÇÃO DE CURSO",
            "meses": [
                ("01/05/2026 até 31/05/2026", datetime.timedelta(hours=2, minutes=28),
                 datetime.timedelta(hours=17, minutes=16), datetime.timedelta(hours=14, minutes=48),
                 datetime.timedelta(0)),
                ("01/06/2026 até 30/06/2026", "-03:11", "05:00", "08:11", "00:00"),
            ],
            "total": ("-00:42", datetime.timedelta(hours=22, minutes=17), datetime.timedelta(hours=22, minutes=59), datetime.timedelta(0)),
        },
    ])

    colaboradores = ler_colaboradores(caminho)

    assert len(colaboradores) == 1
    c = colaboradores[0]
    assert c.nome == "ANA CARLA CRISTOVAO DA SILVA"
    assert c.funcao == "ASSISTENTE DE COORDENAÇÃO"
    assert c.admissao == datetime.date(2026, 5, 13)
    assert c.departamento == "COORDENAÇÃO DE CURSO"
    assert len(c.meses) == 2
    assert c.meses[0].inicio == datetime.date(2026, 5, 1)
    assert c.meses[0].fim == datetime.date(2026, 5, 31)
    assert c.meses[0].total_min == 148
    assert c.meses[1].total_min == -191
    assert c.total_bruto_min == -42
    assert c.credito_total_min == 1337
    assert c.debito_total_min == 1379


def test_ler_colaboradores_bloco_incompleto_usa_fallback(workbook_path, capsys):
    caminho = workbook_path([
        {
            "nome": "FULANO SEM DADOS",
            "funcao": "ESTAGIARIO",
            "admissao": None,
            "departamento": None,
            "meses": [
                ("01/06/2026 até 30/06/2026", datetime.timedelta(0), datetime.timedelta(0),
                 datetime.timedelta(0), datetime.timedelta(0)),
            ],
            "total": (datetime.timedelta(0), datetime.timedelta(0), datetime.timedelta(0), datetime.timedelta(0)),
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
            "meses": [("01/06/2026 até 30/06/2026", datetime.timedelta(hours=1),
                       datetime.timedelta(hours=1), datetime.timedelta(0), datetime.timedelta(0))],
            "total": (datetime.timedelta(hours=1), datetime.timedelta(hours=1), datetime.timedelta(0), datetime.timedelta(0)),
        },
        {
            "nome": "PESSOA DOIS", "funcao": "CARGO B", "admissao": "01/02/2020",
            "departamento": "BIBLIOTECA",
            "meses": [("01/06/2026 até 30/06/2026", datetime.timedelta(hours=-1),
                       datetime.timedelta(0), datetime.timedelta(hours=1), datetime.timedelta(0))],
            "total": ("-01:00", datetime.timedelta(0), datetime.timedelta(hours=1), datetime.timedelta(0)),
        },
    ])

    colaboradores = ler_colaboradores(caminho)

    assert [c.nome for c in colaboradores] == ["PESSOA UM", "PESSOA DOIS"]
    assert colaboradores[0].departamento == "TECNOLOGIA"
    assert colaboradores[1].departamento == "BIBLIOTECA"
