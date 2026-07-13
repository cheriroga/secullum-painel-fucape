import json
from pathlib import Path


def carregar_config(caminho: Path) -> dict[str, str]:
    """Carrega o mapa departamento -> e-mail do gestor. Retorna {} se o
    arquivo ainda não existir (primeira execução)."""
    if not caminho.exists():
        return {}
    return json.loads(caminho.read_text(encoding="utf-8"))


def salvar_config(caminho: Path, mapa: dict[str, str]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(mapa, ensure_ascii=False, indent=2), encoding="utf-8")
