"""Tests for the prompt configuration in sample_db.config."""

from __future__ import annotations

import dataclasses

import pytest

from sample_db.config import get_config


def test_get_config_returns_prompt_defaults() -> None:
    config = get_config()

    assert config.dialect == "PostgreSQL"
    assert config.top_k == 5


def test_get_config_returns_cached_instance() -> None:
    assert get_config() is get_config()


def test_prompt_config_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        get_config().dialect = "PostgreSQL"
