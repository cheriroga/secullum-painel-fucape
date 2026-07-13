import json
import subprocess
from pathlib import Path


class DeployError(RuntimeError):
    pass


def publicar(pasta_base: Path) -> str:
    """Publica pasta_base (a raiz acumulada de todos os períodos já
    gerados) no Netlify e retorna a URL base do site, sem barra final."""
    resultado = subprocess.run(
        ["netlify", "deploy", "--prod", "--dir", str(pasta_base), "--json"],
        capture_output=True, text=True,
    )
    if resultado.returncode != 0:
        raise DeployError(f"Falha ao publicar no Netlify: {resultado.stderr.strip()}")

    dados = json.loads(resultado.stdout)
    url = dados.get("deploy_url") or dados.get("url")
    if not url:
        raise DeployError("Netlify não retornou uma URL de publicação.")
    return url.rstrip("/")
