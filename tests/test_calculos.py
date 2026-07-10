import datetime
from painel_horas.parser import Colaborador, Mes
from painel_horas.calculos import (
    dept_label, saldo_trabalhado_min, is_config, montar_relatorio,
    LIMITE_DEBITO_CONFIG_MIN, TOLERANCIA_CREDITO_CONFIG_RATIO,
)


def _colab(nome, departamento, admissao, meses_totais, total_bruto=None, credito_total=None, debito_total=None):
    """meses_totais: lista de (inicio, fim, total, credito, debito)"""
    meses = [
        Mes(inicio=i, fim=f, total_min=t, credito_min=c, debito_min=d, ajuste_min=0)
        for (i, f, t, c, d) in meses_totais
    ]
    return Colaborador(
        nome=nome, funcao="Cargo Teste", admissao=admissao, departamento=departamento,
        meses=meses,
        total_bruto_min=total_bruto if total_bruto is not None else sum(m.total_min for m in meses),
        credito_total_min=credito_total if credito_total is not None else sum(m.credito_min for m in meses),
        debito_total_min=debito_total if debito_total is not None else sum(m.debito_min for m in meses),
    )


def test_dept_label_agrupa_csc():
    assert dept_label("CONTROLADORIA") == "Centro de Serviços Compartilhados"
    assert dept_label("Comercial") == "Centro de Serviços Compartilhados"
    assert dept_label("FINANCEIRO") == "Centro de Serviços Compartilhados"


def test_dept_label_mantem_outros():
    assert dept_label("TECNOLOGIA") == "Tecnologia"
    assert dept_label("HUB FUCAPE") == "Hub Fucape"


def test_saldo_trabalhado_filtra_meses_antes_da_admissao():
    c = _colab(
        "Recem Admitido", "TECNOLOGIA", admissao=datetime.date(2026, 5, 13),
        meses_totais=[
            (datetime.date(2026, 4, 1), datetime.date(2026, 4, 30), -18000, 0, 18000),  # antes da admissão
            (datetime.date(2026, 5, 1), datetime.date(2026, 5, 31), 363, 363, 0),        # 6h03 depois da admissão
        ],
    )
    assert saldo_trabalhado_min(c) == 363


def test_saldo_trabalhado_sem_admissao_usa_total():
    c = _colab(
        "Sem Data", "TECNOLOGIA", admissao=None,
        meses_totais=[(datetime.date(2026, 5, 1), datetime.date(2026, 5, 31), 100, 100, 0)],
    )
    assert saldo_trabalhado_min(c) == 100


def test_is_config_detecta_debito_padrao_sem_credito():
    c = _colab(
        "Isento", "DIRETORIA", admissao=datetime.date(2020, 1, 1),
        meses_totais=[(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), -21600, 0, 21600)],
    )
    assert is_config(c) is True


def test_is_config_falso_quando_ha_credito_real():
    c = _colab(
        "Com Ponto", "TECNOLOGIA", admissao=datetime.date(2020, 1, 1),
        meses_totais=[(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), 100, 200, 100)],
    )
    assert is_config(c) is False


def test_is_config_falso_quando_debito_abaixo_do_limite():
    c = _colab(
        "Debito Pequeno", "TECNOLOGIA", admissao=datetime.date(2020, 1, 1),
        meses_totais=[(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), -100, 0, 100)],
    )
    assert is_config(c) is False


def test_limites_config_batem_com_o_spec():
    assert LIMITE_DEBITO_CONFIG_MIN == 300 * 60
    assert TOLERANCIA_CREDITO_CONFIG_RATIO == 0.05


def test_is_config_true_quando_credito_residual_e_pequena_fracao_do_debito():
    # THIAGO SOUZA DOS SANTOS (dado real): trabalhou de verdade em janeiro
    # (826 min de crédito) antes do débito padrão de config tomar conta do
    # resto do período (25580 min de débito) — crédito é só 3.2% do débito,
    # deve continuar sendo classificado como config/isento.
    c = _colab(
        "Thiago", "MARKETING", admissao=datetime.date(2022, 4, 4),
        meses_totais=[
            (datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), 626, 826, 200),
            (datetime.date(2026, 2, 1), datetime.date(2026, 2, 28), 0, 0, 0),
            (datetime.date(2026, 5, 1), datetime.date(2026, 5, 31), -10560, 0, 10560),
            (datetime.date(2026, 6, 1), datetime.date(2026, 6, 30), -11100, 0, 11100),
            (datetime.date(2026, 7, 1), datetime.date(2026, 7, 9), -3720, 0, 3720),
        ],
    )
    assert is_config(c) is True


def test_is_config_falso_quando_credito_e_fracao_grande_do_debito():
    c = _colab(
        "Meio a Meio", "TECNOLOGIA", admissao=datetime.date(2020, 1, 1),
        meses_totais=[(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), -9000, 9000, 27000)],
    )
    # débito 27000 min (>=300h), crédito 9000 min = 33% do débito -> não é config
    assert is_config(c) is False


def test_montar_relatorio_geral_gera_kpis_gauge_ranking_e_deptos():
    positivo = _colab(
        "Credor Grande", "HUB FUCAPE", admissao=datetime.date(2020, 1, 1),
        meses_totais=[(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), 6775, 6775, 0)],
    )  # +112h55
    negativo = _colab(
        "Devedor", "TECNOLOGIA", admissao=datetime.date(2020, 1, 1),
        meses_totais=[(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), -1181, 0, 1181)],
    )  # -19h41
    isento = _colab(
        "Config", "DIRETORIA", admissao=datetime.date(2020, 1, 1),
        meses_totais=[(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), -21600, 0, 21600)],
    )

    r = montar_relatorio([positivo, negativo, isento], escopo="geral")

    assert r["contadores"] == {"total": 3, "elegiveis": 2, "nao_elegiveis": 1}
    assert r["ranking"][0]["nome"] == "Credor Grande"
    assert r["ranking"][0]["classe"] == "p"
    assert r["ranking"][0]["valor_fmt"] == "+112h55"
    # +112h55 (6775 min) > escala de 2400 min -> barra travada no teto (50%)
    assert r["ranking"][0]["pct"] == 50.0
    assert r["nota_ranking"] is not None and "Credor" in r["nota_ranking"]
    assert r["ranking"][1]["nome"] == "Devedor"
    assert r["ranking"][1]["classe"] == "n"

    assert r["gauge"]["qtd_passivo"] == 1
    assert r["gauge"]["qtd_receber"] == 1
    assert r["gauge"]["pos_fmt"] == "+112h55"
    assert r["gauge"]["neg_fmt"] == "−19h41"
    assert round(r["gauge"]["neg_pct"] + r["gauge"]["pos_pct"], 4) == 100.0

    assert r["kpis"]["nao_elegiveis"]["valor"] == 1
    assert r["kpis"]["concentracao"]["valor_fmt"] == "+112h55"
    assert r["kpis"]["concentracao"]["pct_fmt"] == "100%"

    assert r["alerta"] is not None and "1 registro" in r["alerta"]

    # "Diretoria" tem só o colaborador "Config" (não elegível), então some do grid
    # de departamentos — a seção 02 só soma saldo de gente com ponto ativo.
    nomes_deptos = {d["nome"] for d in r["deptos"]}
    assert nomes_deptos == {"Hub Fucape", "Tecnologia"}

    assert r["nao_elegiveis_lista"][0]["nome"] == "Config"
    assert r["nao_elegiveis_lista"][0]["valor_fmt"] == "−360h00"


def test_montar_relatorio_depto_sem_deptos_e_subtitulo_admissao():
    recente = _colab(
        "Recem Chegado", "COORDENAÇÃO DE CURSO", admissao=datetime.date(2026, 5, 13),
        meses_totais=[
            (datetime.date(2026, 4, 1), datetime.date(2026, 4, 30), -18000, 0, 18000),
            (datetime.date(2026, 5, 1), datetime.date(2026, 5, 31), 363, 363, 0),
        ],
        total_bruto=-17637,
    )
    r = montar_relatorio([recente], escopo="depto")
    assert r["deptos"] is None
    assert "admitido 13/05/2026" in r["ranking"][0]["subtitulo"]
    assert "desde admissão: +6h03" in r["ranking"][0]["subtitulo"]


def test_montar_relatorio_csc_mostra_time_original():
    membro = _colab(
        "Pessoa CSC", "Controladoria", admissao=datetime.date(2020, 1, 1),
        meses_totais=[(datetime.date(2026, 1, 1), datetime.date(2026, 1, 31), 100, 100, 0)],
    )
    r = montar_relatorio([membro], escopo="csc")
    assert r["ranking"][0]["subtitulo"] == "Controladoria"
