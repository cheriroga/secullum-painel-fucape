import pathlib

from jinja2 import Environment, FileSystemLoader

_DIR_TEMPLATES = pathlib.Path(__file__).resolve().parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_DIR_TEMPLATES)),
    autoescape=True,
)


def render_pagina(contexto: dict) -> str:
    template = _env.get_template("painel.html.j2")
    return template.render(**contexto)


def render_pessoa(contexto: dict) -> str:
    template = _env.get_template("pessoa.html.j2")
    return template.render(**contexto)
