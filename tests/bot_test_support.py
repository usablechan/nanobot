from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

runner = CliRunner()


@contextmanager
def patched_config_paths(config_path: Path):
    with patch("nanobot.config.paths.get_config_path", return_value=config_path), \
         patch("nanobot.config.loader.get_config_path", return_value=config_path):
        yield
