import datetime
from painel_horas.parser import Colaborador, Dia
from painel_horas.calculos import (
    dept_label, saldo_trabalhado_min, sem_batida_real, montar_relatorio,
)


def _dia(data, btotal_min=None, com_batida=True):
    """Cria um Dia de teste. com_batida=True simula uma hora real de entrada;
    com_batida=False simula um código de status (sem batida real nesse dia)."""
    ent1 = datetime.timedelta(hours=8) if com_batida else "FALTA"
    return Dia(
        data=data, dia_semana="Seg",
        ent1=ent1, sai1=None, ent2=None, sai2=None, ent3=None, sai3=None,
        ex50_min=0, atraso_min=0, btotal_min=btotal_min, exnot_min=0,
    )


def _colab(nome, departamento, admissao, dias):
    total = sum(d.btotal_min or 0 for d in dias)
    return Colaborador(
        nome=nome, funcao="Cargo Teste", admissao=admissao, departamento=departamento,
        dias=dias, total_bruto_min=total,
    )


def test_dept_label_agrupa_csc():
    assert dept_label("CONTROLADORIA") == "Centro de Serviços Compartilhados"
    assert dept_label("Administrativo") == "Centro de Serviços Compartilhados"
    assert dept_label("FINANCEIRO") == "Centro de Serviços Compartilhados"


def test_dept_label_mantem_outros():
    assert dept_label("TECNOLOGIA") == "Tecnologia"
    assert dept_label("HUB FUCAPE") == "Hub Fucape"
    assert dept_label("COMERCIAL") == "Comercial"


def test_saldo_trabalhado_filtra_dias_antes_da_admissao():
    c = _colab(
        "Recem Admitido", "TECNOLOGIA", admissao=datetime.date(2026, 5, 13),
        dias=[
            _dia(datetime.date(2026, 4, 20), btotal_min=-300),  # antes da admissão
            _dia(datetime.date(2026, 5, 15), btotal_min=363),   # depois da admissão (6h03)
        ],
    )
    assert saldo_trabalhado_min(c) == 363


def test_saldo_trabalhado_sem_admissao_usa_total():
    c = _colab(
        "Sem Data", "TECNOLOGIA", admissao=None,
        dias=[_dia(datetime.date(2026, 5, 15), btotal_min=100)],
    )
    assert saldo_trabalhado_min(c) == 100


def test_sem_batida_real_true_quando_nenhum_dia_tem_hora_real():
    c = _colab(
        "Isento", "DIRETORIA", admissao=datetime.date(2020, 1, 1),
        dias=[_dia(datetime.date(2026, 1, d), btotal_min=-480, com_batida=False) for d in range(1, 6)],
    )
    assert sem_batida_real(c) is True


def test_sem_batida_real_false_quando_ha_pelo_menos_um_dia_com_batida():
    c = _colab(
        "Com Ponto", "TECNOLOGIA", admissao=datetime.date(2020, 1, 1),
        dias=[
            _dia(datetime.date(2026, 1, 1), btotal_min=-480, com_batida=False),
            _dia(datetime.date(2026, 1, 2), btotal_min=30, com_batida=True),
        ],
    )
    assert sem_batida_real(c) is False


def test_montar_relatorio_geral_gera_kpis_gauge_ranking_e_deptos():
    positivo = _colab(
        "Credor Grande", "HUB FUCAPE", admissao=datetime.date(2020, 1, 1),
        dias=[_dia(datetime.date(2026, 1, 15), btotal_min=6775)],
    )  # +112h55
    negativo = _colab(
        "Devedor", "TECNOLOGIA", admissao=datetime.date(2020, 1, 1),
        dias=[_dia(datetime.date(2026, 1, 15), btotal_min=-1181)],
    )  # -19h41
    isento = _colab(
        "Config", "DIRETORIA", admissao=datetime.date(2020, 1, 1),
        dias=[_dia(datetime.date(2026, 1, d), btotal_min=-720, com_batida=False) for d in range(1, 31)],
    )  # -360h00, sem nenhuma batida real

    r = montar_relatorio([positivo, negativo, isento], escopo="geral", prefixo_pessoas="deptos/pessoas/")

    assert r["contadores"] == {"total": 3, "elegiveis": 2, "nao_elegiveis": 1}
    assert r["ranking"][0]["nome"] == "Credor Grande"
    assert r["ranking"][0]["classe"] == "p"
    assert r["ranking"][0]["valor_fmt"] == "+112h55"
    assert r["ranking"][0]["pessoa_href"] == "deptos/pessoas/credor-grande.html"
    # +112h55 (6775 min) > escala de 2400 min -> barra travada no teto (50%)
    assert r["ranking"][0]["pct"] == 50.0
    assert r["nota_ranking"] is not None and "Credor" in r["nota_ranking"]
    assert r["ranking"][1]["nome"] == "Devedor"
    assert r["ranking"][1]["classe"] == "n"
    assert r["ranking"][1]["pessoa_href"] == "deptos/pessoas/devedor.html"

    assert r["gauge"]["qtd_passivo"] == 1
    assert r["gauge"]["qtd_receber"] == 1
    assert r["gauge"]["pos_fmt"] == "+112h55"
    assert r["gauge"]["neg_fmt"] == "−19h41"
    assert round(r["gauge"]["neg_pct"] + r["gauge"]["pos_pct"], 4) == 100.0

    assert r["kpis"]["nao_elegiveis"]["valor"] == 1
    assert r["kpis"]["concentracao"]["valor_fmt"] == "+112h55"
    assert r["kpis"]["concentracao"]["pct_fmt"] == "100%"

    assert r["alerta"] is not None and "1 registro" in r["alerta"]

    # "Diretoria" tem só o colaborador "Config" (sem batida real), então some do grid
    # de departamentos — a seção 02 só soma saldo de gente com ponto ativo.
    nomes_deptos = {d["nome"] for d in r["deptos"]}
    assert nomes_deptos == {"Hub Fucape", "Tecnologia"}

    assert r["nao_elegiveis_lista"][0]["nome"] == "Config"
    assert r["nao_elegiveis_lista"][0]["valor_fmt"] == "−360h00"


def test_montar_relatorio_depto_sem_deptos_e_subtitulo_admissao():
    recente = _colab(
        "Recem Chegado", "COORDENAÇÃO DE CURSO", admissao=datetime.date(2026, 5, 13),
        dias=[
            _dia(datetime.date(2026, 4, 20), btotal_min=-18000),
            _dia(datetime.date(2026, 5, 15), btotal_min=363),
        ],
    )
    r = montar_relatorio([recente], escopo="depto")
    assert r["deptos"] is None
    assert "admitido 13/05/2026" in r["ranking"][0]["subtitulo"]
    assert "desde admissão: +6h03" in r["ranking"][0]["subtitulo"]


def test_montar_relatorio_csc_mostra_time_original():
    membro = _colab(
        "Pessoa CSC", "Controladoria", admissao=datetime.date(2020, 1, 1),
        dias=[_dia(datetime.date(2026, 1, 15), btotal_min=100)],
    )
    r = montar_relatorio([membro], escopo="csc")
    assert r["ranking"][0]["subtitulo"] == "Controladoria"
