#!/usr/bin/env python3
"""Build verifier evidence for every recorded S2 oracle result.

Admission-side only. No Docker/model/treatment/holdout operation is performed.
"""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import ndv_build_s2_verifier_evidence as builder

def load(p:Path)->Any: return json.loads(p.read_text(encoding='utf-8'))
def sha256_file(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as fh:
        for c in iter(lambda:fh.read(1024*1024),b''): h.update(c)
    return h.hexdigest()
def require_file(p:Path,label:str)->Path:
    p=p.resolve()
    if not p.is_file(): raise ValueError(f'{label} not found: {p}')
    return p

def main()->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--oracle-receipt',required=True,type=Path); ap.add_argument('--execution-plan',required=True,type=Path); ap.add_argument('--out-root',type=Path,default=Path('.ndv-corpus/s2-w01/verifier')); ap.add_argument('--receipt',type=Path,default=Path('.ndv-corpus/s2-w01/verifier-batch-receipt.json')); args=ap.parse_args()
    oracle_path=require_file(args.oracle_receipt,'oracle receipt'); plan_path=require_file(args.execution_plan,'execution plan'); oracle,plan=load(oracle_path),load(plan_path)
    if oracle.get('schema_id')!='ndv-p1-s2-oracle-batch-receipt-v1' or oracle.get('status')!='ORACLE_BATCH_RECORDED': raise SystemExit('VERIFIER_BATCH_BLOCKED: oracle batch receipt required')
    if plan.get('schema_id')!='ndv-p1-s2-base-audit-execution-plan-v1': raise SystemExit('VERIFIER_BATCH_BLOCKED: execution plan v1 required')
    if oracle.get('execution_plan_sha256')!=sha256_file(plan_path): raise SystemExit('VERIFIER_BATCH_BLOCKED: oracle/plan hash mismatch')
    if oracle.get('model_execution')!='NONE' or oracle.get('treatment_execution')!='NOT_EXECUTED' or oracle.get('holdout_access')!='NONE': raise SystemExit('VERIFIER_BATCH_BLOCKED: oracle receipt contaminated')
    by_id={e['candidate_id']:e for e in plan.get('entries',[])}; results=[]
    for item in oracle.get('results',[]):
        cid=item.get('candidate_id'); entry=by_id.get(cid); oref=item.get('oracle_ref')
        if item.get('status')!='RECORDED' or entry is None or not isinstance(oref,str): results.append({'candidate_id':cid,'status':'BLOCKED','reason':'ORACLE_NOT_RECORDED'}); continue
        opath=require_file(Path(oref),f'{cid} oracle');
        if item.get('oracle_sha256')!=sha256_file(opath): results.append({'candidate_id':cid,'status':'BLOCKED','reason':'ORACLE_HASH_MISMATCH'}); continue
        oracle_payload=load(opath); admission_path=require_file(Path(entry['admission_only_ref']),f'{cid} admission'); admission=load(admission_path)
        prov=dict(oracle_payload.get('parser_provenance') or {}); prov['parser_name']=oracle_payload.get('parser_name')
        try: built=builder.build(admission,prov)
        except Exception as exc: results.append({'candidate_id':cid,'status':'BLOCKED','reason':f'VERIFIER_BUILD_FAILED: {exc}'}); continue
        out=(args.out_root/cid).resolve()
        if out.exists(): results.append({'candidate_id':cid,'status':'BLOCKED','reason':'VERIFIER_OUTPUT_EXISTS'}); continue
        out.mkdir(parents=True)
        builder.write(out/'focal-verifier.json',built['focal']); builder.write(out/'preservation-verifier.json',built['preservation']); builder.write(out/'verifier-provenance.json',built['provenance'])
        bundle={'schema_id':'ndv-p1-s2-verifier-evidence-bundle-v2','instance_id':built['focal']['instance_id'],'source_row_index':built['focal']['source_row_index'],'focal_ref':str((out/'focal-verifier.json').resolve()),'focal_sha256':builder.sha256(built['focal']),'preservation_ref':str((out/'preservation-verifier.json').resolve()),'preservation_sha256':builder.sha256(built['preservation']),'provenance_ref':str((out/'verifier-provenance.json').resolve()),'provenance_sha256':builder.sha256(built['provenance']),'treatment_execution':'NOT_EXECUTED','holdout_access':'NONE'}
        builder.write(out/'bundle.json',bundle); results.append({'candidate_id':cid,'status':'RECORDED','bundle_ref':str((out/'bundle.json').resolve()),'bundle_file_sha256':sha256_file(out/'bundle.json'),'oracle_classification':oracle_payload.get('classification')})
    receipt={'schema_id':'ndv-p1-s2-verifier-batch-receipt-v1','status':'VERIFIER_BATCH_RECORDED','oracle_receipt_ref':str(oracle_path),'oracle_receipt_sha256':sha256_file(oracle_path),'execution_plan_ref':str(plan_path),'execution_plan_sha256':sha256_file(plan_path),'results':results,'model_execution':'NONE','treatment_execution':'NOT_EXECUTED','holdout_access':'NONE','completed_at':datetime.now(timezone.utc).isoformat()}
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    if args.receipt.exists(): raise SystemExit(f'refusing overwrite: {args.receipt}')
    args.receipt.write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps({'status':receipt['status'],'receipt':str(args.receipt),'results':results},indent=2)); return 0 if all(r.get('status')=='RECORDED' for r in results) else 2
if __name__=='__main__': raise SystemExit(main())
