import subprocess

import pytest

from webapp import deploy_netlify


def test_publicar_retorna_url_sem_barra_final(tmp_path, monkeypatch):
    def fake_run(comando, capture_output, text):
        assert comando[:3] == ["netlify", "deploy", "--prod"]
        assert str(tmp_path) in comando
        return subprocess.CompletedProcess(
            comando, returncode=0, stdout='{"deploy_url": "https://painel-fucape.netlify.app/"}', stderr="",
        )

    monkeypatch.setattr(deploy_netlify.subprocess, "run", fake_run)

    url = deploy_netlify.publicar(tmp_path)

    assert url == "https://painel-fucape.netlify.app"


def test_publicar_com_falha_do_cli_levanta_deploy_error(tmp_path, monkeypatch):
    def fake_run(comando, capture_output, text):
        return subprocess.CompletedProcess(comando, returncode=1, stdout="", stderr="not authenticated")

    monkeypatch.setattr(deploy_netlify.subprocess, "run", fake_run)

    with pytest.raises(deploy_netlify.DeployError):
        deploy_netlify.publicar(tmp_path)
