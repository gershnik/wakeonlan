# pylint: disable=missing-module-docstring, missing-function-docstring

import nox
import re
from pathlib import Path

mydir = Path(__file__).parent

extraPythons = []
if (mydir/".extrapythons").exists():
    with open(mydir/".extrapythons", "r", encoding="utf-8") as extraPythonsFile:
        for line in extraPythonsFile:
            line = line.strip()
            if len(line) != 0 and not re.match(r'\s*#.*', line):
                extraPythons.append(line.strip())

@nox.session(python=["3.7", "3.8", "3.9", "3.10", "3.11", "3.12", "3.13", "3.13t"] + extraPythons)
def test(session):
    session.install("pytest")
    #session.install("--no-build-isolation", "--editable", ".")
    session.install(".")
    session.run("pytest")

