import json
from pathlib import Path


def carregar_config(caminho: Path) -> dict:
    """Carrega o e-mail do CEO e o mapa departamento -> e-mail do gestor.
    Retorna a config vazia (nenhum e-mail configurado) se o arquivo ainda
    não existir (primeira execução)."""
    if not caminho.exists():
        return {"ceo_email": "", "gestores": {}}
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    return {"ceo_email": dados.get("ceo_email", ""), "gestores": dados.get("gestores", {})}


def salvar_config(caminho: Path, config: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def tem_algum_email(config: dict) -> bool:
    return bool(config.get("ceo_email")) or bool(config.get("gestores"))
