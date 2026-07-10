import pathlib

from jinja2 import Environment, FileSystemLoader, select_autoescape

_DIR_TEMPLATES = pathlib.Path(__file__).resolve().parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_DIR_TEMPLATES)),
    autoescape=select_autoescape(["html"]),
)


def render_pagina(contexto: dict) -> str:
    template = _env.get_template("painel.html.j2")
    return template.render(**contexto)
