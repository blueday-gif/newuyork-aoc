"""Streamlit Community Cloud 배포 준비 정적 점검. 외부 파일·네트워크를 쓰지 않는다."""
import ast
import json
import os
import re
import sys
import tomllib
from pathlib import Path

QDIR = Path(__file__).resolve().parents[1]
APP_FILES = [
    QDIR / "app.py",
    QDIR / "qlib.py",
    QDIR / "state.py",
    *sorted((QDIR / "components").glob("*.py")),
    *sorted((QDIR / "app_pages").glob("*.py")),
]
LOCAL = {"qlib", "state", "components", "app_pages"}
ALLOWED = {"streamlit", "pandas", "altair"}
NO_STATS = {21, 22, 48}

_DRIVE = re.compile(r"[A-Za-z]:[\\/]")
_URL = re.compile(r"https?://\S+")


def _assert_exact_case(names: set[str], expected: str) -> None:
    """소문자로 같은 이름이 있으면, 원래 집합에도 정확한 이름이 있어야 한다."""
    if expected.lower() in {n.lower() for n in names}:
        assert expected in names, expected


def _top_level_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue
            if node.module is None:
                continue
            names.add(node.module.split(".")[0])
    return names


def test_app_imports_allowed():
    found: set[str] = set()
    for path in APP_FILES:
        found |= _top_level_imports(path)
    external = {
        n for n in found
        if n not in sys.stdlib_module_names and n not in LOCAL
    }
    assert external <= ALLOWED, f"허용 밖 import: {sorted(external - ALLOWED)}"


def test_requirements_cover_imports():
    names = set()
    for line in (QDIR / "requirements.txt").read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        names.add(s.split(">=")[0].split("==")[0].strip().lower())
    assert names == ALLOWED


def test_no_absolute_paths():
    paths = list(APP_FILES)
    paths += sorted((QDIR / "content").glob("*.toml"))
    paths += sorted((QDIR / "meta").iterdir())
    bad = []
    for path in paths:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        for i, line in enumerate(text.splitlines(), 1):
            cleaned = _URL.sub("", line)
            if _DRIVE.search(cleaned) or "/Users/" in cleaned or "/home/" in cleaned:
                bad.append(f"{path.relative_to(QDIR)}:{i}: {line.strip()[:80]}")
    assert not bad, "절대 경로:\n" + "\n".join(bad)


def test_app_does_not_read_raw():
    forbidden = ("parquet", "NY311_RAW", "NY311_EXT", "geopandas", "D:/ny311")
    bad = []
    for path in APP_FILES:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                bad.append(f"{path.relative_to(QDIR)}: {token}")
    assert not bad, "원본 읽기 흔적:\n" + "\n".join(bad)


def test_data_files_exact_case():
    meta = json.loads((QDIR / "meta" / "questions.json").read_text(encoding="utf-8"))
    content_names = set(os.listdir(QDIR / "content"))
    data_names = set(os.listdir(QDIR / "data"))
    data_lower = {n.lower() for n in data_names}
    missing = set()
    for q in meta["questions"]:
        qid = q["id"]
        toml_name = f"q{qid:03d}.toml"
        json_name = f"q{qid:03d}.json"
        assert toml_name in content_names, toml_name
        if json_name.lower() in data_lower:
            assert json_name in data_names, json_name
        else:
            missing.add(qid)
    assert missing == NO_STATS, missing

    labs_names = set(os.listdir(QDIR / "data" / "labs"))
    assert "small_denominator.json" in labs_names
    assert "did_containerization.json" in labs_names

    joined_names = set(os.listdir(QDIR / "data" / "joined"))
    for name in joined_names:
        low = name.lower()
        if re.fullmatch(r"q\d{3}\.json", low):
            _assert_exact_case(joined_names, low)


def test_app_data_size():
    total = 0
    for sub in ("data", "content", "meta"):
        for root, _, files in os.walk(QDIR / sub):
            for name in files:
                total += (Path(root) / name).stat().st_size
    assert total <= 20 * 1024 * 1024, f"{total / 1e6:.1f}MB > 20MB"


def test_streamlit_config():
    cfg_path = QDIR.parent / ".streamlit" / "config.toml"
    cfg = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    assert cfg.get("browser", {}).get("gatherUsageStats") is False
    assert not (QDIR.parent / ".streamlit" / "secrets.toml").exists()
