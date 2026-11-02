#!/usr/bin/env python3
"""Build the Document Sanitizer release folder (ADR-001) with no third-party packages.

Writes releases/addons/document-sanitizer/<version>/ holding:
  document-sanitizer-<version>.zip  function code only; the Function App installs requirements.txt
  azuredeploy.json                  infra/main.bicep compiled with the Azure CLI's Bicep
  deploy.ps1, quickstart.en.md, quickstart.es.md
  SHA256SUMS

The output is reproducible: fixed zip timestamps, sorted entries, sorted checksums.
An existing version folder is never overwritten (bump VERSION instead).

Usage:
  python3 package.py                        # into <repo>/releases
  python3 package.py --out-root <dir> --bicep "az bicep"
"""
import argparse
import hashlib
import io
import shlex
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ADDON = Path(__file__).resolve().parent
ZIP_DATE = (1980, 1, 1, 0, 0, 0)  # fixed timestamps -> reproducible zips
FUNCTION_FILES = ("function_app.py", "host.json", "requirements.txt")
FUNCTION_DIRS = ("app", "config")
SUPPORT_FILES = ("deploy.ps1", "quickstart.en.md", "quickstart.es.md")


class BuildError(Exception):
    pass


def _function_names(addon: Path) -> list[str]:
    names = list(FUNCTION_FILES)
    for directory in FUNCTION_DIRS:
        for path in (addon / directory).rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                names.append(path.relative_to(addon).as_posix())
    return sorted(names)


def build_function_zip(addon: Path) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in _function_names(addon):
            info = zipfile.ZipInfo(name, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, (addon / name).read_bytes())
    return buffer.getvalue()


def compile_bicep(addon: Path, command: str, outfile: Path) -> None:
    argv = shlex.split(command) + [
        "build",
        "--file", str(addon / "infra" / "main.bicep"),
        "--outfile", str(outfile),
    ]
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        raise BuildError(
            f"cannot run '{command}': the Azure CLI with Bicep is required to compile infra/main.bicep "
            "(install it, or pass --bicep with the command that runs it)"
        ) from None
    if completed.returncode != 0 or not outfile.exists():
        raise BuildError(f"bicep build failed: {completed.stderr.strip()[:500]}")


def build_release(addon: Path, out_root: Path, bicep_command: str = "az bicep") -> Path:
    version = (addon / "VERSION").read_text(encoding="utf-8").strip()
    target = Path(out_root) / "addons" / "document-sanitizer" / version
    if target.exists():
        raise BuildError(f"{target} already exists; bump VERSION to publish a new release")
    missing = [name for name in SUPPORT_FILES if not (addon / name).is_file()]
    if missing:
        raise BuildError(f"missing release files: {', '.join(missing)}")

    zip_name = f"document-sanitizer-{version}.zip"
    with tempfile.TemporaryDirectory() as scratch:
        template = Path(scratch) / "azuredeploy.json"
        compile_bicep(addon, bicep_command, template)
        files = {
            zip_name: build_function_zip(addon),
            "azuredeploy.json": template.read_bytes(),
        }
    for name in SUPPORT_FILES:
        files[name] = (addon / name).read_bytes()

    sums = "".join(f"{hashlib.sha256(data).hexdigest()}  {name}\n" for name, data in sorted(files.items()))
    target.mkdir(parents=True)
    for name, data in files.items():
        (target / name).write_bytes(data)
    (target / "SHA256SUMS").write_bytes(sums.encode("utf-8"))
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Build the Document Sanitizer release folder.")
    parser.add_argument("--out-root", type=Path, default=ADDON.parents[1] / "releases")
    parser.add_argument("--bicep", default="az bicep", help="command that runs 'build' for Bicep")
    args = parser.parse_args(argv)
    try:
        target = build_release(ADDON, args.out_root, args.bicep)
    except BuildError as error:
        print(f"package: {error}", file=sys.stderr)
        return 1
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
