import datetime


def parse_horas(valor) -> int:
    """Normaliza um valor de hora do extrato Secullum para minutos assinados."""
    if valor is None:
        return 0
    if isinstance(valor, datetime.timedelta):
        return int(valor.total_seconds() // 60)
    if isinstance(valor, str):
        texto = valor.strip()
        negativo = texto.startswith("-")
        texto = texto.lstrip("+-")
        horas_str, minutos_str = texto.split(":")
        total = int(horas_str) * 60 + int(minutos_str)
        return -total if negativo else total
    raise TypeError(f"valor de hora inesperado: {valor!r}")


def format_horas(minutos: int) -> str:
    """Formata minutos assinados como '+217h16' / '−3h11'."""
    sinal = "+" if minutos >= 0 else "−"
    minutos_abs = abs(minutos)
    horas, resto = divmod(minutos_abs, 60)
    return f"{sinal}{horas}h{resto:02d}"
