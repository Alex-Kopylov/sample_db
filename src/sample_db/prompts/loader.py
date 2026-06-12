"""Jinja2 environment and rendering helper for the prompt templates."""

from __future__ import annotations

from jinja2 import Environment, PackageLoader, StrictUndefined

_env = Environment(
    loader=PackageLoader("sample_db", "prompts"),
    undefined=StrictUndefined,
    autoescape=False,  # noqa: S701 - prompts are plain text, not HTML.
    keep_trailing_newline=False,
)


def render_prompt(template_name: str, **context: object) -> str:
    """Render the named prompt template with the given context."""
    return _env.get_template(template_name).render(**context).strip()
