import pytest


@pytest.fixture(autouse=True)
def fixed_today(monkeypatch):
    """Polis contoh punya tanggal mulai dan berakhir, jadi semua test memakai tanggal tetap."""
    monkeypatch.setenv("CC_TODAY", "2026-10-18")
