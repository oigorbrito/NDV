import unittest
import ndv_assemble_s2_audit_state as mod

class AuditAssemblerTests(unittest.TestCase):
    def test_pure_digest_normalizes_repo_digest(self):
        self.assertEqual(mod.pure_digest('docker.io/org/repo@sha256:'+'a'*64),'sha256:'+'a'*64)
        self.assertIsNone(mod.pure_digest('docker.io/org/repo:tag'))
    def test_index_rejects_duplicate_candidate(self):
        with self.assertRaisesRegex(ValueError,'duplicate candidate_id'):
            mod.index([{'candidate_id':'c1'},{'candidate_id':'c1'}])
    def test_index_requires_array(self):
        with self.assertRaisesRegex(ValueError,'expected array'):
            mod.index({})

if __name__=='__main__': unittest.main()
