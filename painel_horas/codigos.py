import json
import random
import string
from pathlib import Path

# Alfabeto dos códigos de URL: letras minúsculas + dígitos. Sem maiúsculas nem
# caracteres ambíguos removidos de propósito — o objetivo é só impedir que um
# gestor adivinhe a URL de outro departamento, não resistir a brute force.
_ALFABETO = string.ascii_lowercase + string.digits
_COMPRIMENTO = 6

# Rótulo reservado do painel do CEO (visão geral) no dicionário de códigos.
# Não colide com nome de departamento real; garante que o CEO também ganhe uma
# pasta de código opaco, sem URL adivinhável.
LABEL_CEO = "CEO (painel geral)"


def caminho_dicionario(raiz: Path) -> Path:
    """Caminho canônico do dicionário departamento -> código. Fica em
    webapp_data/ (que já está no .gitignore e não é publicado no deploy),
    então o mapeamento nunca vai pro git nem pro site público."""
    return raiz / "webapp_data" / "deptos_codigos.json"


class MapaCodigos:
    """Mapeia rótulo de departamento -> código opaco de URL, de forma estável:
    uma vez atribuído, o código de um departamento nunca muda (fica gravado no
    dicionário em disco). Departamentos novos ganham código na primeira vez que
    são pedidos via .codigo()."""

    def __init__(self, mapa: dict[str, str], caminho: Path | None = None, rng: random.Random | None = None):
        self._mapa = dict(mapa)
        self._caminho = caminho
        self._rng = rng or random.Random()

    @classmethod
    def carregar(cls, caminho: Path, rng: random.Random | None = None) -> "MapaCodigos":
        mapa = json.loads(caminho.read_text(encoding="utf-8")) if caminho.exists() else {}
        return cls(mapa, caminho, rng)

    def codigo(self, label: str) -> str:
        if label not in self._mapa:
            self._mapa[label] = self._gerar()
        return self._mapa[label]

    def _gerar(self) -> str:
        usados = set(self._mapa.values())
        while True:
            codigo = "".join(self._rng.choice(_ALFABETO) for _ in range(_COMPRIMENTO))
            tem_letra = any(c.isalpha() for c in codigo)
            tem_digito = any(c.isdigit() for c in codigo)
            if tem_letra and tem_digito and codigo not in usados:
                return codigo

    def salvar(self) -> None:
        if self._caminho is None:
            return
        self._caminho.parent.mkdir(parents=True, exist_ok=True)
        self._caminho.write_text(
            json.dumps(self._mapa, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
