from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from eci.config import Settings


@pytest.fixture
def test_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        vector_backend="local",
        vector_index_path=tmp_path / "vectors.json",
        embedding_backend="local",
        answer_backend="local",
        raw_data_dir=tmp_path / "raw",
        processed_data_dir=tmp_path / "processed",
        rejected_data_dir=tmp_path / "rejected",
        log_dir=tmp_path / "logs",
        hmac_secret="a-test-secret-that-is-long-enough-for-repeatable-tests",
    )
