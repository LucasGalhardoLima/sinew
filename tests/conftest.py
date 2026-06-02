import os, sys, sqlite3, subprocess, pathlib
import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DB = ROOT / "dist" / "sinew.sqlite"


@pytest.fixture(scope="session")
def con():
    if not DB.exists():
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src")}
        subprocess.run([sys.executable, "-m", "sinew.build"], cwd=ROOT, env=env, check=True)
    c = sqlite3.connect(DB)
    yield c
    c.close()
