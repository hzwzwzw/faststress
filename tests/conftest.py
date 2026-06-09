import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path):
    """Isolate tests from real ~/.faststress data."""
    with patch("faststress.storage.DATA_DIR", tmp_path):
        (tmp_path / "presets").mkdir()
        (tmp_path / "results").mkdir()
        yield tmp_path
