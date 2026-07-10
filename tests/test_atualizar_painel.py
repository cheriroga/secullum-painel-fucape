import datetime
from pathlib import Path

from atualizar_painel import encontrar_xlsx_mais_recente, gerar_painel


def test_encontrar_xlsx_mais_recente_vazio(tmp_path):
    assert encontrar_xlsx_mais_recente(tmp_path) is None


def test_encontrar_xlsx_mais_recente_escolhe_o_mais_novo(tmp_path):
    antigo = tmp_path / "antigo.xlsx"
    novo = tmp_path / "novo.xlsx"
    antigo.write_bytes(b"x")
    novo.write_bytes(b"y")
    import os
    import time
    os.utime(antigo, (time.time() - 100, time.time() - 100))
    assert encontrar_xlsx_mais_recente(tmp_path) == novo


def test_gerar_painel_cria_index_e_paginas_de_departamento(tmp_path, workbook_path):
    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "meses": [("01/06/2026 até 30/06/2026", datetime.timedelta(hours=5),
                       datetime.timedelta(hours=5), datetime.timedelta(0), datetime.timedelta(0))],
            "total": (datetime.timedelta(hours=5), datetime.timedelta(hours=5), datetime.timedelta(0), datetime.timedelta(0)),
        },
        {
            "nome": "PESSOA CONTROLADORIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "CONTROLADORIA",
            "meses": [("01/06/2026 até 30/06/2026", datetime.timedelta(hours=-2),
                       datetime.timedelta(0), datetime.timedelta(hours=2), datetime.timedelta(0))],
            "total": ("-02:00", datetime.timedelta(0), datetime.timedelta(hours=2), datetime.timedelta(0)),
        },
        {
            "nome": "PESSOA ADMINISTRATIVO", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "ADMINISTRATIVO",
            "meses": [("01/06/2026 até 30/06/2026", datetime.timedelta(hours=1),
                       datetime.timedelta(hours=1), datetime.timedelta(0), datetime.timedelta(0))],
            "total": (datetime.timedelta(hours=1), datetime.timedelta(hours=1), datetime.timedelta(0), datetime.timedelta(0)),
        },
    ])
    pasta_saida = tmp_path / "painel"

    resumo = gerar_painel(caminho, pasta_saida)

    assert resumo["colaboradores"] == 3
    assert resumo["departamentos"] == 2  # Tecnologia + CSC (Controladoria+Administrativo)
    assert (pasta_saida / "index.html").exists()
    assert (pasta_saida / "deptos" / "tecnologia.html").exists()
    assert (pasta_saida / "deptos" / "centro-servicos-compartilhados.html").exists()
    assert not (pasta_saida / "deptos" / "controladoria.html").exists()

    conteudo_csc = (pasta_saida / "deptos" / "centro-servicos-compartilhados.html").read_text(encoding="utf-8")
    assert "PESSOA CONTROLADORIA" in conteudo_csc
    assert "PESSOA ADMINISTRATIVO" in conteudo_csc
    # subtexto de rastreabilidade do time original
    assert "Controladoria" in conteudo_csc
    assert "Administrativo" in conteudo_csc


def test_gerar_painel_remove_paginas_de_departamento_obsoletas(tmp_path, workbook_path):
    pasta_saida = tmp_path / "painel"

    caminho_v1 = workbook_path([
        {
            "nome": "PESSOA MARKETING", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "MARKETING",
            "meses": [("01/06/2026 até 30/06/2026", datetime.timedelta(hours=1),
                       datetime.timedelta(hours=1), datetime.timedelta(0), datetime.timedelta(0))],
            "total": (datetime.timedelta(hours=1), datetime.timedelta(hours=1), datetime.timedelta(0), datetime.timedelta(0)),
        },
    ])
    gerar_painel(caminho_v1, pasta_saida)
    assert (pasta_saida / "deptos" / "marketing.html").exists()

    caminho_v2 = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "meses": [("01/06/2026 até 30/06/2026", datetime.timedelta(hours=1),
                       datetime.timedelta(hours=1), datetime.timedelta(0), datetime.timedelta(0))],
            "total": (datetime.timedelta(hours=1), datetime.timedelta(hours=1), datetime.timedelta(0), datetime.timedelta(0)),
        },
    ])
    gerar_painel(caminho_v2, pasta_saida)

    # marketing.html não existe mais nesta rodada — o arquivo obsoleto da
    # rodada anterior não pode continuar no ar com dado desatualizado.
    assert not (pasta_saida / "deptos" / "marketing.html").exists()
    assert (pasta_saida / "deptos" / "tecnologia.html").exists()


def test_main_sem_xlsx_nao_gera_nada_e_avisa(tmp_path, monkeypatch, capsys):
    import atualizar_painel
    monkeypatch.setattr(atualizar_painel, "__file__", str(tmp_path / "atualizar_painel.py"))
    (tmp_path / "extratos").mkdir()

    atualizar_painel.main()

    saida = capsys.readouterr()
    assert "erro" in saida.out
    assert not (tmp_path / "painel").exists()
