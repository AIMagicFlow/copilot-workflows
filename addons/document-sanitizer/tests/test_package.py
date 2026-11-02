import hashlib
import shutil
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

ADDON = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ADDON))
import package  # noqa: E402

FAKE_BICEP = """\
import pathlib, sys
args = sys.argv[1:]
out = pathlib.Path(args[args.index("--outfile") + 1])
out.write_text('{"fake": "arm template"}', encoding="utf-8")
"""


def make_fixture_tree(root: Path) -> Path:
    """A copy of the add-on's shippable files, with a stub for each file that Task 13 adds."""
    addon = root / "addon"
    addon.mkdir()
    for name in ("function_app.py", "host.json", "requirements.txt", "VERSION"):
        shutil.copy(ADDON / name, addon / name)
    (addon / "VERSION").write_text("9.9.9\n", encoding="utf-8")
    shutil.copytree(ADDON / "app", addon / "app", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ADDON / "config", addon / "config")
    (addon / "infra").mkdir()
    (addon / "infra" / "main.bicep").write_text("// stub\n", encoding="utf-8")
    (addon / "deploy.ps1").write_text("# stub\n", encoding="utf-8")
    (addon / "quickstart.en.md").write_text("# stub\n", encoding="utf-8")
    (addon / "quickstart.es.md").write_text("# stub\n", encoding="utf-8")
    (addon / "local.settings.json").write_text('{"Values": {}}', encoding="utf-8")
    (addon / "tests").mkdir()
    (addon / "tests" / "test_x.py").write_text("", encoding="utf-8")
    return addon


def fake_bicep_command(root: Path) -> str:
    script = root / "fake_bicep.py"
    script.write_text(FAKE_BICEP, encoding="utf-8")
    return f"{sys.executable} {script}"


class PackageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addon = make_fixture_tree(self.tmp)

    def test_zip_is_byte_identical_across_builds(self):
        first = package.build_function_zip(self.addon)
        second = package.build_function_zip(self.addon)

        self.assertEqual(first, second)

    def test_zip_has_function_code_and_no_extras(self):
        data = package.build_function_zip(self.addon)
        names = zipfile.ZipFile(__import__("io").BytesIO(data)).namelist()

        self.assertIn("function_app.py", names)
        self.assertIn("host.json", names)
        self.assertIn("requirements.txt", names)
        self.assertIn("app/api.py", names)
        self.assertIn("config/redaction-profiles.json", names)
        self.assertEqual(names, sorted(names))
        for excluded in ("tests/", "infra/", "connector/", "local.settings.json", "__pycache__", "deploy.ps1"):
            self.assertFalse(any(excluded in name for name in names), excluded)

    def test_release_is_reproducible_and_sums_match_files(self):
        command = fake_bicep_command(self.tmp)
        first = package.build_release(self.addon, self.tmp / "out1", command)
        second = package.build_release(self.addon, self.tmp / "out2", command)

        for name in ("document-sanitizer-9.9.9.zip", "azuredeploy.json", "deploy.ps1"):
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes(), name)
        sums = (first / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
        self.assertEqual(sums, (second / "SHA256SUMS").read_text(encoding="utf-8").splitlines())
        for line in sums:
            digest, name = line.split("  ", 1)
            self.assertEqual(hashlib.sha256((first / name).read_bytes()).hexdigest(), digest, name)
        self.assertEqual([line.split("  ", 1)[1] for line in sums], sorted(line.split("  ", 1)[1] for line in sums))

    def test_release_folder_has_the_adr_files(self):
        out = package.build_release(self.addon, self.tmp / "out", fake_bicep_command(self.tmp))

        self.assertEqual(out, self.tmp / "out" / "addons" / "document-sanitizer" / "9.9.9")
        for name in (
            "document-sanitizer-9.9.9.zip",
            "azuredeploy.json",
            "deploy.ps1",
            "quickstart.en.md",
            "quickstart.es.md",
            "SHA256SUMS",
        ):
            self.assertTrue((out / name).is_file(), name)

    def test_missing_bicep_fails_loudly(self):
        with self.assertRaises(package.BuildError) as ctx:
            package.build_release(self.addon, self.tmp / "out", "no-such-bicep-command-xyz")

        self.assertIn("Bicep", str(ctx.exception))
        self.assertFalse((self.tmp / "out").exists())

    def test_existing_version_is_not_overwritten(self):
        command = fake_bicep_command(self.tmp)
        package.build_release(self.addon, self.tmp / "out", command)

        with self.assertRaises(package.BuildError):
            package.build_release(self.addon, self.tmp / "out", command)


if __name__ == "__main__":
    unittest.main()
