
# pylint: disable=missing-function-docstring,missing-module-docstring

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

tmpdir = tempfile.TemporaryDirectory()
os.environ['WAKEONLAN_HOME'] = tmpdir.name


@pytest.fixture(autouse=True)
def test_home():
    yield tmpdir
    for f in Path(tmpdir.name).glob('*'):
        if f.is_dir():
            shutil.rmtree(f)
        else:
            f.unlink()


@pytest.fixture
def run_cli():
    """Invoke `python -m wakeonlan ...` as a subprocess and return CompletedProcess.

    Inherits the current process's WAKEONLAN_HOME, so each test gets the same
    fresh-per-test temp directory that the rest of the suite uses. Pass
    expect_success=True/False to assert on the return code with diagnostics.
    """
    def _run(*args, expect_success=None, timeout=15):
        result = subprocess.run(
            [sys.executable, '-m', 'wakeonlan', *args],
            capture_output=True, text=True, timeout=timeout, check=False,
        )
        if expect_success is True:
            assert result.returncode == 0, (
                f'expected success, got rc={result.returncode}\n'
                f'stdout:\n{result.stdout}\nstderr:\n{result.stderr}'
            )
        elif expect_success is False:
            assert result.returncode != 0, (
                f'expected failure, got rc={result.returncode}\n'
                f'stdout:\n{result.stdout}\nstderr:\n{result.stderr}'
            )
        return result
    return _run


@pytest.fixture
def write_config():
    """Write a JSON document directly to WAKEONLAN_HOME/.wakeonlan."""
    def _write(data):
        path = Path(os.environ['WAKEONLAN_HOME']) / '.wakeonlan'
        path.write_text(json.dumps(data), encoding='utf-8')
        return path
    return _write
