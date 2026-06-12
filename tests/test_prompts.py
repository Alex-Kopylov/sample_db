"""Tests for sample_db.prompts."""

from __future__ import annotations

import pytest
from jinja2.exceptions import TemplateNotFound, UndefinedError

from sample_db.prompts import render_prompt


def test_generate_query_prompt_renders_expected_text() -> None:
    rendered = render_prompt("generate_query_system.j2", dialect="PostgreSQL", top_k=5)

    assert rendered == """
You are an agent designed to interact with a SQL database.
Given an input question, create a syntactically correct PostgreSQL query to run,
then look at the results of the query and return the answer. Unless the user
specifies a specific number of examples they wish to obtain, always limit your
query to at most 5 results.
You can order the results by a relevant column to return the most interesting
examples in the database. Never query for all the columns from a specific table,
only ask for the relevant columns given the question.

NEVER make any DML statements (INSERT, UPDATE, DELETE, DROP etc.) to the database.
""".strip()


def test_check_query_prompt_renders_expected_text() -> None:
    rendered = render_prompt("check_query_system.j2", dialect="PostgreSQL")

    assert rendered == """
You are a SQL expert with a strong attention to detail.
Double check the PostgreSQL query for common mistakes, including:
- Using NOT IN with NULL values
- Using UNION when UNION ALL should have been used
- Using BETWEEN for exclusive ranges
- Data type mismatch in predicates
- Properly quoting identifiers
- Using the correct number of arguments for functions
- Casting to the correct data type
- Using the proper columns for joins

If there are any of the above mistakes, rewrite the query. If there are no
mistakes, reproduce the original query.

You will call the appropriate tool to execute the query after running this check.
""".strip()


@pytest.mark.parametrize(
    ("template_name", "context"),
    [
        ("generate_query_system.j2", {"dialect": "PostgreSQL", "top_k": 5}),
        ("check_query_system.j2", {"dialect": "PostgreSQL"}),
    ],
)
def test_prompt_rendering_strips_output_and_resolves_jinja_markers(
    template_name: str,
    context: dict[str, object],
) -> None:
    rendered = render_prompt(template_name, **context)

    assert rendered == rendered.strip()
    assert "{{" not in rendered
    assert "{%" not in rendered


def test_missing_variable_raises_undefined_error() -> None:
    with pytest.raises(UndefinedError):
        render_prompt("generate_query_system.j2", dialect="PostgreSQL")


def test_unknown_template_raises_template_not_found() -> None:
    with pytest.raises(TemplateNotFound):
        render_prompt("does_not_exist.j2")
