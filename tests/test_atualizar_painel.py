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


def _dia_com_batida(data_str, btotal_str):
    return (data_str, "Qui", datetime.timedelta(hours=8), datetime.timedelta(hours=17),
            None, None, None, None, None, None, btotal_str, None)


def _dia_sem_batida(data_str, btotal_str):
    return (data_str, "Qui", "FALTA", "FALTA", None, None, None, None, None, None, btotal_str, None)


def test_gerar_painel_cria_index_deptos_e_paginas_de_pessoa(tmp_path, workbook_path):
    caminho = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("01/06/2026", "+05:00")],
        },
        {
            "nome": "PESSOA CONTROLADORIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "CONTROLADORIA",
            "dias": [_dia_com_batida("01/06/2026", "-02:00")],
        },
        {
            "nome": "PESSOA ADMINISTRATIVO", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "ADMINISTRATIVO",
            "dias": [_dia_com_batida("01/06/2026", "+01:00")],
        },
        {
            "nome": "PESSOA ISENTA", "funcao": "DIRETOR", "admissao": "01/01/2020",
            "departamento": "DIRETORIA",
            "dias": [_dia_sem_batida("01/06/2026", "-08:00")],
        },
    ])
    pasta_saida = tmp_path / "painel"

    resumo = gerar_painel(caminho, pasta_saida)

    assert resumo["colaboradores"] == 4
    assert resumo["departamentos"] == 3  # Tecnologia + CSC (Controladoria+Administrativo) + Diretoria
    assert (pasta_saida / "index.html").exists()
    assert (pasta_saida / "deptos" / "tecnologia.html").exists()
    assert (pasta_saida / "deptos" / "centro-servicos-compartilhados.html").exists()
    assert not (pasta_saida / "deptos" / "controladoria.html").exists()

    # páginas de pessoa: uma por colaborador elegível, nenhuma pro isento
    assert (pasta_saida / "deptos" / "pessoas" / "pessoa-tecnologia.html").exists()
    assert (pasta_saida / "deptos" / "pessoas" / "pessoa-controladoria.html").exists()
    assert (pasta_saida / "deptos" / "pessoas" / "pessoa-administrativo.html").exists()
    assert not (pasta_saida / "deptos" / "pessoas" / "pessoa-isenta.html").exists()

    conteudo_dept = (pasta_saida / "deptos" / "tecnologia.html").read_text(encoding="utf-8")
    assert 'href="pessoas/pessoa-tecnologia.html"' in conteudo_dept

    conteudo_index = (pasta_saida / "index.html").read_text(encoding="utf-8")
    assert 'href="deptos/pessoas/pessoa-tecnologia.html"' in conteudo_index


def test_gerar_painel_remove_paginas_obsoletas_de_departamento_e_pessoa(tmp_path, workbook_path):
    pasta_saida = tmp_path / "painel"

    caminho_v1 = workbook_path([
        {
            "nome": "PESSOA MARKETING", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "MARKETING",
            "dias": [_dia_com_batida("01/06/2026", "+01:00")],
        },
    ])
    gerar_painel(caminho_v1, pasta_saida)
    assert (pasta_saida / "deptos" / "marketing.html").exists()
    assert (pasta_saida / "deptos" / "pessoas" / "pessoa-marketing.html").exists()

    caminho_v2 = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("01/06/2026", "+01:00")],
        },
    ])
    gerar_painel(caminho_v2, pasta_saida)

    # arquivos obsoletos da rodada anterior não podem continuar no ar com dado desatualizado
    assert not (pasta_saida / "deptos" / "marketing.html").exists()
    assert not (pasta_saida / "deptos" / "pessoas" / "pessoa-marketing.html").exists()
    assert (pasta_saida / "deptos" / "tecnologia.html").exists()
    assert (pasta_saida / "deptos" / "pessoas" / "pessoa-tecnologia.html").exists()


def test_main_sem_xlsx_nao_gera_nada_e_avisa(tmp_path, monkeypatch, capsys):
    import atualizar_painel
    monkeypatch.setattr(atualizar_painel, "__file__", str(tmp_path / "atualizar_painel.py"))
    (tmp_path / "extratos").mkdir()

    atualizar_painel.main()

    saida = capsys.readouterr()
    assert "erro" in saida.out
    assert not (tmp_path / "painel").exists()
