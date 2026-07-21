import subprocess

import pytest

from webapp import deploy_github


@pytest.fixture(autouse=True)
def worktree_isolado(tmp_path, monkeypatch):
    worktree = tmp_path / "worktree"
    monkeypatch.setattr(deploy_github, "PASTA_WORKTREE", worktree)
    return worktree


def _fake_git_ok(worktree):
    comandos_recebidos = []

    def fake_run(comando, capture_output, text, cwd):
        comandos_recebidos.append(comando)
        if comando[:3] == ["git", "worktree", "add"]:
            worktree.mkdir(parents=True, exist_ok=True)
            (worktree / ".git").mkdir(exist_ok=True)
        return subprocess.CompletedProcess(comando, returncode=0, stdout="", stderr="")

    return fake_run, comandos_recebidos


def _fazer_pasta_base(tmp_path):
    pasta_base = tmp_path / "painel_web"
    pasta_base.mkdir()
    (pasta_base / "2026-06").mkdir()
    (pasta_base / "2026-06" / "index.html").write_text("<html></html>")
    return pasta_base


def test_publicar_roda_git_na_ordem_certa_e_retorna_url(tmp_path, monkeypatch, worktree_isolado):
    fake_run, comandos = _fake_git_ok(worktree_isolado)
    monkeypatch.setattr(deploy_github.subprocess, "run", fake_run)

    pasta_base = _fazer_pasta_base(tmp_path)

    url = deploy_github.publicar(pasta_base)

    assert url == deploy_github.URL_PAGINAS

    comandos_git = [c for c in comandos if c[0] == "git"]
    assert ["git", "fetch", "origin", "gh-pages"] in comandos_git
    assert ["git", "add", "-A"] in comandos_git
    assert ["git", "push", "origin", "HEAD:gh-pages"] in comandos_git


def test_copiar_conteudo_leva_arquivos_de_pasta_base_pro_worktree(tmp_path, worktree_isolado):
    worktree_isolado.mkdir()
    pasta_base = _fazer_pasta_base(tmp_path)

    deploy_github._copiar_conteudo(pasta_base)

    assert (worktree_isolado / "2026-06" / "index.html").read_text() == "<html></html>"


def test_gerar_indice_raiz_lista_periodos_do_mais_recente_pro_mais_antigo(tmp_path):
    pasta_base = tmp_path / "painel_web"
    pasta_base.mkdir()
    (pasta_base / "2026-06").mkdir()
    (pasta_base / "2026-07").mkdir()

    html = deploy_github._gerar_indice_raiz(pasta_base)

    assert html.index("2026-07") < html.index("2026-06")
    assert '<a href="2026-07/">2026-07</a>' in html
    assert '<a href="2026-06/">2026-06</a>' in html


def test_limpar_worktree_remove_conteudo_antigo_preservando_git(worktree_isolado):
    worktree_isolado.mkdir()
    (worktree_isolado / ".git").mkdir()
    (worktree_isolado / "periodo-antigo").mkdir()
    (worktree_isolado / "periodo-antigo" / "index.html").write_text("velho")

    deploy_github._limpar_worktree()

    assert not (worktree_isolado / "periodo-antigo").exists()
    assert (worktree_isolado / ".git").exists()


def test_publicar_com_falha_no_fetch_levanta_deploy_error(tmp_path, monkeypatch, worktree_isolado):
    def fake_run(comando, capture_output, text, cwd):
        if comando[:3] == ["git", "fetch", "origin"]:
            return subprocess.CompletedProcess(comando, returncode=1, stdout="", stderr="network error")
        return subprocess.CompletedProcess(comando, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(deploy_github.subprocess, "run", fake_run)

    with pytest.raises(deploy_github.DeployError):
        deploy_github.publicar(_fazer_pasta_base(tmp_path))


def test_publicar_com_falha_no_push_levanta_deploy_error(tmp_path, monkeypatch, worktree_isolado):
    def fake_run(comando, capture_output, text, cwd):
        if comando[:3] == ["git", "worktree", "add"]:
            worktree_isolado.mkdir(parents=True, exist_ok=True)
            (worktree_isolado / ".git").mkdir(exist_ok=True)
        if comando[:2] == ["git", "push"]:
            return subprocess.CompletedProcess(comando, returncode=1, stdout="", stderr="permission denied")
        return subprocess.CompletedProcess(comando, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(deploy_github.subprocess, "run", fake_run)

    with pytest.raises(deploy_github.DeployError):
        deploy_github.publicar(_fazer_pasta_base(tmp_path))


def test_publicar_sem_mudancas_nao_levanta_erro_no_commit_vazio(tmp_path, monkeypatch, worktree_isolado):
    def fake_run(comando, capture_output, text, cwd):
        if comando[:3] == ["git", "worktree", "add"]:
            worktree_isolado.mkdir(parents=True, exist_ok=True)
            (worktree_isolado / ".git").mkdir(exist_ok=True)
        if comando[:2] == ["git", "commit"]:
            return subprocess.CompletedProcess(comando, returncode=1, stdout="nothing to commit", stderr="")
        return subprocess.CompletedProcess(comando, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(deploy_github.subprocess, "run", fake_run)

    url = deploy_github.publicar(_fazer_pasta_base(tmp_path))

    assert url == deploy_github.URL_PAGINAS
