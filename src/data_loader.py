import json
from pathlib import Path
from src.schemas import Policy

GOLDEN_DIR = Path("data/golden")


def load_policies(directory: Path = GOLDEN_DIR) -> list[Policy]:
    """Baca semua polis (JSON sesuai skema Policy). File berawalan 'sample_' hanya dipakai
    bila belum ada polis asli, jadi polis contoh otomatis hilang saat file Cath masuk."""
    files = sorted(Path(directory).glob("*.json"))
    real = [f for f in files if not f.name.startswith("sample_")]
    chosen = real or files
    return [Policy.model_validate(json.loads(f.read_text(encoding="utf-8"))) for f in chosen]
