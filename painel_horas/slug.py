import unicodedata

CONECTIVOS = {"de", "da", "do", "das", "dos", "e"}


def slugify(nome: str) -> str:
    """Converte um nome de departamento em slug de arquivo, removendo
    acentos e conectivos em português (de/da/do/das/dos/e)."""
    normalizado = unicodedata.normalize("NFKD", nome)
    sem_acento = "".join(c for c in normalizado if not unicodedata.combining(c))
    palavras = [p for p in sem_acento.lower().split() if p not in CONECTIVOS]
    return "-".join(palavras)
