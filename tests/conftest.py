import pytest
import os
import tempfile
import shutil
from pathlib import Path

tmpdir = tempfile.TemporaryDirectory()

os.environ['WAKEONLAN_HOME'] = tmpdir.name

@pytest.fixture(autouse=True)
def testHome():
    yield tmpdir
    for f in Path(tmpdir.name).glob("*"):
        if f.is_dir():
            shutil.rmtree(f)
        else:
            f.unlink()