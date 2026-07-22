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

    # raiz do período só tem o stub neutro; o painel do CEO fica na pasta dele
    conteudo_raiz = (pasta_saida / "index.html").read_text(encoding="utf-8")
    assert "Nada por aqui" in conteudo_raiz
    assert (pasta_saida / resumo["ceo_slug"] / "index.html").exists()

    # cada depto na própria pasta de slug, com index.html dentro
    assert (pasta_saida / "tecnologia" / "index.html").exists()
    assert (pasta_saida / "centro-servicos-compartilhados" / "index.html").exists()
    assert not (pasta_saida / "controladoria").exists()

    # páginas de pessoa: pasta compartilhada, uma por elegível, nenhuma pro isento
    assert (pasta_saida / "pessoas" / "pessoa-tecnologia.html").exists()
    assert (pasta_saida / "pessoas" / "pessoa-controladoria.html").exists()
    assert (pasta_saida / "pessoas" / "pessoa-administrativo.html").exists()
    assert not (pasta_saida / "pessoas" / "pessoa-isenta.html").exists()

    # links entre escopos são relativos e sobem só até a pasta compartilhada/irmã
    conteudo_dept = (pasta_saida / "tecnologia" / "index.html").read_text(encoding="utf-8")
    assert 'href="../pessoas/pessoa-tecnologia.html"' in conteudo_dept

    conteudo_ceo = (pasta_saida / resumo["ceo_slug"] / "index.html").read_text(encoding="utf-8")
    assert 'href="../pessoas/pessoa-tecnologia.html"' in conteudo_ceo
    assert 'href="../tecnologia/"' in conteudo_ceo


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
    assert (pasta_saida / "marketing" / "index.html").exists()
    assert (pasta_saida / "pessoas" / "pessoa-marketing.html").exists()

    caminho_v2 = workbook_path([
        {
            "nome": "PESSOA TECNOLOGIA", "funcao": "ANALISTA", "admissao": "01/01/2020",
            "departamento": "TECNOLOGIA",
            "dias": [_dia_com_batida("01/06/2026", "+01:00")],
        },
    ])
    gerar_painel(caminho_v2, pasta_saida)

    # arquivos obsoletos da rodada anterior não podem continuar no ar com dado desatualizado
    assert not (pasta_saida / "marketing").exists()
    assert not (pasta_saida / "pessoas" / "pessoa-marketing.html").exists()
    assert (pasta_saida / "tecnologia" / "index.html").exists()
    assert (pasta_saida / "pessoas" / "pessoa-tecnologia.html").exists()


def test_main_sem_xlsx_nao_gera_nada_e_avisa(tmp_path, monkeypatch, capsys):
    import atualizar_painel
    monkeypatch.setattr(atualizar_painel, "__file__", str(tmp_path / "atualizar_painel.py"))
    (tmp_path / "extratos").mkdir()

    atualizar_painel.main()

    saida = capsys.readouterr()
    assert "erro" in saida.out
    assert not (tmp_path / "painel").exists()
