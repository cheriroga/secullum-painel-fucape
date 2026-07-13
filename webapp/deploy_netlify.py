import json
import os
import subprocess
from pathlib import Path


class DeployError(RuntimeError):
    pass


def publicar(pasta_base: Path) -> str:
    """Publica pasta_base (a raiz acumulada de todos os períodos já
    gerados) no Netlify e retorna a URL base do site, sem barra final."""
    resultado = subprocess.run(
        ["netlify", "deploy", "--prod", "--dir", str(pasta_base), "--json"],
        capture_output=True, text=True, shell=(os.name == "nt"),
    )
    if resultado.returncode != 0:
        raise DeployError(f"Falha ao publicar no Netlify: {resultado.stderr.strip()}")

    try:
        dados = json.loads(resultado.stdout)
    except json.JSONDecodeError as exc:
        raise DeployError(f"Netlify não retornou um JSON válido: {exc}") from exc
    url = dados.get("deploy_url") or dados.get("url")
    if not url:
        raise DeployError("Netlify não retornou uma URL de publicação.")
    return url.rstrip("/")
