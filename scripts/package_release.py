"""Package a reviewable source release. Never includes credentials, databases or runtime caches."""
import argparse
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED


def package(output):
    root = Path(__file__).resolve().parents[1]
    directories = ["outreach", "scripts", "deploy", "docs", "examples", "tests", ".github"]
    files = ["README.md", "PLAN.md", "VALIDATION.md", "pyproject.toml", "requirements.lock", "Dockerfile",
             "compose.yaml", "compose.platform-browser.yaml", ".env.example", ".gitignore", ".dockerignore"]
    output.parent.mkdir(parents=True, exist_ok=True)
    paths = [root / name for name in files]
    for directory in directories:
        paths.extend(p for p in (root / directory).rglob("*") if p.is_file()
                     and "__pycache__" not in p.parts and p.suffix not in {".pyc", ".db", ".log"})
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path in sorted(paths):
            archive.write(path, path.relative_to(root).as_posix())
    with ZipFile(output) as archive:
        names = archive.namelist()
        assert all(name != ".env" and not name.startswith(("data/", ".venv/")) for name in names)
        assert archive.testzip() is None
    print(f"Created verified source release: {output.resolve()} ({len(paths)} files)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("dist/outreach-workbench.zip"))
    package(parser.parse_args().output)
