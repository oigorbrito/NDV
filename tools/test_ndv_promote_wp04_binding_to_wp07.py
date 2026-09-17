import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import ndv_promote_wp04_binding_to_wp07 as mod


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class PromotionTests(unittest.TestCase):
    def write_registry(self, root: Path) -> Path:
        p = root / "registry.json"
        p.write_text(json.dumps({
            "schema_id":"ndv-p1-wp07-treatment-bindings-v1",
            "status":"INCOMPLETE_BINDING_COVERAGE",
            "treatments":{
                "B4":{"name":"LOCAL_OR_FREE_FIRST","required_roles":["PRIMARY_LOCAL_OR_FREE","ESCALATION_STRONG"],"bindings":{},"status":"UNBOUND"}
            },
            "treatment_execution":"NOT_EXECUTED","holdout_access":"NONE"
        }))
        return p

    def write_import(self, root: Path, *, surface="LOCAL_PINNED", tamper=False) -> Path:
        d = root / "binding-import"; d.mkdir()
        qualification = {"status":"S0_READY"}
        qbytes = (json.dumps(qualification, sort_keys=True)+"\n").encode()
        binding = {
            "schema_id":"ndv-p1-wp04-executor-binding-v2","status":"QUALIFIED",
            "binding_id":"BIND-1","exact_executor_identity":"aider+qwen",
            "qualification_evidence_sha256":sha(qbytes),"surface_class":surface,
            "dynamic_routing":False,"implicit_fallback":False,"automatic_download":False
        }
        bbytes = (json.dumps(binding, sort_keys=True)+"\n").encode()
        (d/"executor-binding-v2.json").write_bytes(bbytes)
        (d/"qualification-evidence.json").write_bytes(qbytes)
        receipt = {
            "schema_id":"ndv-wp04-binding-import-receipt-v2",
            "status":"ORIGINAL_BINDING_AND_QUALIFICATION_PRESERVED",
            "binding_id":"BIND-1","exact_executor_identity":"aider+qwen",
            "binding_file_sha256":sha(bbytes),"binding_file_size_bytes":len(bbytes),
            "qualification_file_sha256":sha(qbytes),"qualification_file_size_bytes":len(qbytes),
            "binding_reconstructed":False,"qualification_reconstructed":False,
            "treatment_reexecuted":False,"holdout_access":"NONE"
        }
        (d/"binding-import-receipt.json").write_text(json.dumps(receipt))
        if tamper:
            (d/"qualification-evidence.json").write_text("{}")
        return d

    def test_local_wp04_binding_promotes_only_b4_first_hop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); registry=self.write_registry(root); imp=self.write_import(root)
            result=mod.promote(registry, imp, root)
            b4=result["treatments"]["B4"]
            self.assertEqual(b4["status"],"PARTIALLY_BOUND")
            self.assertIn("PRIMARY_LOCAL_OR_FREE",b4["bindings"])
            self.assertNotIn("ESCALATION_STRONG",b4["bindings"])
            self.assertEqual(b4["bindings"]["PRIMARY_LOCAL_OR_FREE"]["role_scope"],"B4.PRIMARY_LOCAL_OR_FREE_ONLY")

    def test_remote_surface_is_not_promoted_as_local_first_hop(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); registry=self.write_registry(root); imp=self.write_import(root,surface="STRONG_REMOTE_PINNED")
            with self.assertRaisesRegex(ValueError,"requires LOCAL_PINNED/HOSTED_FREE_PINNED"):
                mod.promote(registry,imp,root)

    def test_tampered_qualification_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); registry=self.write_registry(root); imp=self.write_import(root,tamper=True)
            with self.assertRaisesRegex(ValueError,"qualification hash/size mismatch"):
                mod.promote(registry,imp,root)

    def test_existing_b4_first_hop_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); registry=self.write_registry(root); imp=self.write_import(root)
            payload=json.loads(registry.read_text()); payload["treatments"]["B4"]["bindings"]["PRIMARY_LOCAL_OR_FREE"]={"binding_id":"existing"}; registry.write_text(json.dumps(payload))
            with self.assertRaisesRegex(ValueError,"already populated"):
                mod.promote(registry,imp,root)

    def test_evidence_outside_artifact_root_blocks(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as ext:
            root=Path(tmp); registry=self.write_registry(root); imp=self.write_import(Path(ext))
            with self.assertRaisesRegex(ValueError,"must be inside artifact root"):
                mod.promote(registry,imp,root)


if __name__=="__main__": unittest.main()
