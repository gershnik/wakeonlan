import nox
import re
from pathlib import Path

mydir = Path(__file__).parent

extraPythons = []
if (mydir/".extrapythons").exists():
    with open(mydir/".extrapythons", "r") as extraPythonsFile:
        for line in extraPythonsFile:
            line = line.strip()
            if len(line) != 0 and not re.match(r'\s*#.*', line):
                extraPythons.append(line.strip())

@nox.session(python=["3.7", "3.8", "3.9", "3.10", "3.11", "3.12"] + extraPythons)
def test(session):
    session.install("pytest")
    #session.install("--no-build-isolation", "--editable", ".")
    session.install(".")
    session.run("pytest")

