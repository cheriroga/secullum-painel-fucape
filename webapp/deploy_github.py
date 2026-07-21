import shutil
import subprocess
from pathlib import Path

RAIZ_REPO = Path(__file__).resolve().parent.parent
PASTA_WORKTREE = RAIZ_REPO / ".gh-pages-worktree"
BRANCH = "gh-pages"
URL_PAGINAS = "https://cheriroga.github.io/secullum-painel-fucape"


class DeployError(RuntimeError):
    pass


def _git(*args, cwd=None):
    resultado = subprocess.run(
        ["git", *args], capture_output=True, text=True, cwd=cwd or RAIZ_REPO,
    )
    if resultado.returncode != 0:
        raise DeployError(f"Falha ao publicar no GitHub Pages: {resultado.stderr.strip()}")
    return resultado.stdout


def _limpar_worktree():
    for item in PASTA_WORKTREE.iterdir():
        if item.name == ".git":
            continue
        if item.is_dir():
            shutil.rmtree(item)
        else:
            item.unlink()


def _copiar_conteudo(pasta_base: Path):
    for item in pasta_base.iterdir():
        destino = PASTA_WORKTREE / item.name
        if item.is_dir():
            shutil.copytree(item, destino)
        else:
            shutil.copy2(item, destino)


def publicar(pasta_base: Path) -> str:
    """Publica pasta_base inteira na branch gh-pages do GitHub Pages e retorna
    a URL base do site, sem barra final. Espera que a branch gh-pages já
    exista no repositório remoto (criada uma vez com `git checkout --orphan gh-pages`)."""
    if PASTA_WORKTREE.exists():
        shutil.rmtree(PASTA_WORKTREE)
    _git("worktree", "prune")

    _git("fetch", "origin", BRANCH)
    _git("worktree", "add", str(PASTA_WORKTREE), f"origin/{BRANCH}", "-B", BRANCH)

    _limpar_worktree()
    _copiar_conteudo(pasta_base)
    (PASTA_WORKTREE / ".nojekyll").touch()

    _git("add", "-A", cwd=PASTA_WORKTREE)
    commit = subprocess.run(
        ["git", "commit", "-m", "deploy: atualiza painel"],
        capture_output=True, text=True, cwd=PASTA_WORKTREE,
    )
    if commit.returncode != 0 and "nothing to commit" not in commit.stdout:
        raise DeployError(f"Falha ao publicar no GitHub Pages: {commit.stderr.strip()}")

    _git("push", "origin", f"HEAD:{BRANCH}", cwd=PASTA_WORKTREE)

    shutil.rmtree(PASTA_WORKTREE, ignore_errors=True)
    _git("worktree", "prune")

    return URL_PAGINAS
