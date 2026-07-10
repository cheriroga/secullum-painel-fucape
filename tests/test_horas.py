import datetime
from painel_horas.horas import parse_horas, format_horas


def test_parse_horas_timedelta_positivo():
    assert parse_horas(datetime.timedelta(hours=2, minutes=28)) == 148


def test_parse_horas_timedelta_zero():
    assert parse_horas(datetime.timedelta(0)) == 0


def test_parse_horas_none():
    assert parse_horas(None) == 0


def test_parse_horas_string_negativa():
    assert parse_horas("-03:11") == -191


def test_parse_horas_string_negativa_grande():
    # débito de config isento pode passar de 24h: -360:00
    assert parse_horas("-360:00") == -21600


def test_parse_horas_string_positiva_com_sinal_explicito():
    assert parse_horas("+00:12") == 12


def test_parse_horas_string_positiva_grande_com_sinal_explicito():
    assert parse_horas("+112:55") == 6775


def test_format_horas_positivo():
    assert format_horas(148) == "+2h28"


def test_format_horas_negativo():
    assert format_horas(-191) == "−3h11"


def test_format_horas_zero():
    assert format_horas(0) == "+0h00"
