import tempfile
import unittest
from pathlib import Path

from ndv_verify_df501_structural import verify


BASE_CLI = '''\nclass SQLiteMissionStore: pass\nclass SQLiteEventLedger: pass\nclass SQLiteExecutionHandleStore: pass\ndef main(argv=None):\n    store = SQLiteMissionStore()\n    if True:\n        command = "doctor"\n        if command == "doctor":\n            from metao.doctor import run_doctor\n            return run_doctor()\n'''

SOLVED_CLI = '''\nclass SQLiteMissionStore: pass\nclass SQLiteEventLedger: pass\nclass SQLiteExecutionHandleStore: pass\ndef load_factory_callable(spec):\n    return lambda **kwargs: None\ndef _load_operator(spec):\n    return load_factory_callable(spec)\ndef main(argv=None):\n    command = "doctor"\n    if command == "doctor":\n        from metao.doctor import run_doctor\n        return run_doctor()\n    store = SQLiteMissionStore()\n'''

SOLVED_DOCTOR = 'from metao.cli import load_factory_callable\ndef run_doctor():\n    return load_factory_callable("x:y")\n'
SOLVED_ENTRY = 'from metao.cli import load_factory_callable\ndef f():\n    return load_factory_callable("x:y")\n'


class DF501StructuralVerifierTests(unittest.TestCase):
    def make_repo(self, cli: str, doctor: str, entry: str) -> Path:
        root = Path(self.tmp.name)
        pkg = root / "src" / "metao"
        pkg.mkdir(parents=True, exist_ok=True)
        (pkg / "cli.py").write_text(cli, encoding="utf-8")
        (pkg / "doctor.py").write_text(doctor, encoding="utf-8")
        (pkg / "entrypoint.py").write_text(entry, encoding="utf-8")
        return root

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_base_like_shape_fails(self):
        root = self.make_repo(BASE_CLI, 'def run_doctor():\n    return {}\n', 'def f():\n    return None\n')
        self.assertEqual(verify(root)["status"], "FAIL")

    def test_requirement_shape_passes(self):
        root = self.make_repo(SOLVED_CLI, SOLVED_DOCTOR, SOLVED_ENTRY)
        result = verify(root)
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(all(result["checks"].values()))


if __name__ == "__main__":
    unittest.main()
