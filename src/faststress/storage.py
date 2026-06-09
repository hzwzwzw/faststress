from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from .models import BenchResult, Preset, TestCase, TestGroup

DATA_DIR = Path.home() / ".faststress"


def ensure_data_dir():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "presets").mkdir(exist_ok=True)
    (DATA_DIR / "results").mkdir(exist_ok=True)


def save_group(group: TestGroup, path: Optional[Path] = None):
    ensure_data_dir()
    if path is None:
        path = DATA_DIR / f"{group.name}.json"
    path.write_text(group.model_dump_json(indent=2))


def load_group(path: Path) -> TestGroup:
    data = json.loads(path.read_text())
    return TestGroup.model_validate(data)


def list_groups() -> list[Path]:
    ensure_data_dir()
    return sorted(DATA_DIR.glob("*.json"))


def save_preset(preset: Preset):
    ensure_data_dir()
    path = DATA_DIR / "presets" / f"{preset.name}.json"
    path.write_text(preset.model_dump_json(indent=2))


def load_preset(name: str) -> Optional[Preset]:
    path = DATA_DIR / "presets" / f"{name}.json"
    if not path.exists():
        return None
    return Preset.model_validate(json.loads(path.read_text()))


def list_presets() -> list[str]:
    ensure_data_dir()
    return [p.stem for p in (DATA_DIR / "presets").glob("*.json")]


def delete_preset(name: str):
    path = DATA_DIR / "presets" / f"{name}.json"
    if path.exists():
        path.unlink()


def export_cases(cases: list[TestCase], path: Path):
    data = [c.model_dump() for c in cases]
    path.write_text(json.dumps(data, indent=2))


def import_cases(path: Path) -> list[TestCase]:
    data = json.loads(path.read_text())
    return [TestCase.model_validate(item) for item in data]


def save_result_csv(case_name: str, result: BenchResult):
    ensure_data_dir()
    results_dir = DATA_DIR / "results"
    csv_path = results_dir / f"{case_name}.csv"
    is_new = not csv_path.exists()

    fields = ["timestamp"] + list(BenchResult.model_fields.keys())
    row = {"timestamp": datetime.now().isoformat()}
    row.update(result.model_dump())

    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if is_new:
            writer.writeheader()
        writer.writerow(row)
