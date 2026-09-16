import tempfile
import unittest
from pathlib import Path

from ndv_verify_df601_structural import check


class DF601StructuralVerifierTests(unittest.TestCase):
    def make_workspace(self, persistence: str, shadow: str) -> Path:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        p = root / "experiments/rust-chassis-a/metao-contracts/tests"
        s = root / "experiments/rust-chassis-a/metao-testkit/tests"
        p.mkdir(parents=True)
        s.mkdir(parents=True)
        (p / "discovery_persistence_tests.rs").write_text(persistence, encoding="utf-8")
        (s / "phase6_shadow.rs").write_text(shadow, encoding="utf-8")
        return root

    def test_base_like_fixture_fails(self):
        root = self.make_workspace(
            "SystemTime::now(); std::env::temp_dir();",
            'std::env::var("CARGO_BIN_EXE_metao-wire-runtime"); Path::new("target");',
        )
        self.assertFalse(all(check(root).values()))

    def test_requirement_fixture_passes(self):
        root = self.make_workspace(
            "use std::sync::atomic::AtomicU64; NEXT.fetch_add(1, Ordering::Relaxed); std::process::id();",
            'std::env::var("CARGO_BIN_EXE_metao-wire-runtime"); std::env::var_os("CARGO_TARGET_DIR"); let target_root = 1;',
        )
        self.assertTrue(all(check(root).values()))


if __name__ == "__main__":
    unittest.main()
