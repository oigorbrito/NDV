#!/usr/bin/env python3
"""Interpret all recorded S2 base audits from one image-bound execution receipt.

Read-only post-audit tooling: no Docker execution, model call, treatment, patch
application, or holdout access.
"""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def load(p: Path)->Any: return json.loads(p.read_text(encoding='utf-8'))
def sha256_file(p: Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as fh:
        for c in iter(lambda:fh.read(1024*1024),b''): h.update(c)
    return h.hexdigest()
def require_file(p:Path,label:str)->Path:
    p=p.resolve()
    if not p.is_file(): raise ValueError(f'{label} not found: {p}')
    return p

def validate_inputs(receipt_path:Path, plan_path:Path)->tuple[dict[str,Any],dict[str,Any]]:
    receipt_path=require_file(receipt_path,'base audit execution receipt'); plan_path=require_file(plan_path,'execution plan')
    receipt,plan=load(receipt_path),load(plan_path)
    if receipt.get('schema_id')!='ndv-p1-s2-base-audit-execution-receipt-v1' or receipt.get('status')!='BASE_AUDIT_BATCH_RECORDED': raise ValueError('recorded base-audit receipt required')
    if plan.get('schema_id')!='ndv-p1-s2-base-audit-execution-plan-v1' or plan.get('status')!='AUDIT_EXECUTION_PLAN_READY': raise ValueError('execution plan v1 required')
    if receipt.get('plan_file_sha256')!=sha256_file(plan_path): raise ValueError('execution receipt/plan hash mismatch')
    if receipt.get('model_execution')!='NONE' or receipt.get('treatment_execution')!='NOT_EXECUTED' or receipt.get('holdout_access')!='NONE': raise ValueError('execution receipt contamination')
    if receipt.get('selected_candidate_ids')!=[e.get('candidate_id') for e in plan.get('entries',[])]: raise ValueError('execution receipt candidate order/set mismatch')
    return receipt,plan

def main()->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--execution-receipt',required=True,type=Path); ap.add_argument('--execution-plan',required=True,type=Path); ap.add_argument('--upstream-root',required=True,type=Path); ap.add_argument('--interpreter',type=Path,default=Path('tools/ndv_interpret_s2_base_oracle.py')); ap.add_argument('--out-root',type=Path,default=Path('.ndv-corpus/s2-w01/oracle')); ap.add_argument('--receipt',type=Path,default=Path('.ndv-corpus/s2-w01/oracle-batch-receipt.json')); args=ap.parse_args()
    try: receipt,plan=validate_inputs(args.execution_receipt,args.execution_plan)
    except (OSError,ValueError,json.JSONDecodeError) as exc: print(json.dumps({'status':'FAIL','reason':'ORACLE_BATCH_BLOCKED','detail':str(exc)},indent=2)); return 2
    interpreter=require_file(args.interpreter,'oracle interpreter'); by_id={e['candidate_id']:e for e in plan['entries']}; results=[]
    for recorded in receipt.get('results',[]):
        cid=recorded.get('candidate_id'); entry=by_id.get(cid); report_ref=recorded.get('report_ref')
        if entry is None or not isinstance(report_ref,str): results.append({'candidate_id':cid,'status':'BLOCKED','reason':'MISSING_RECORDED_BASE_REPORT'}); continue
        report=require_file(Path(report_ref),f'{cid} base report')
        if recorded.get('report_sha256')!=sha256_file(report): results.append({'candidate_id':cid,'status':'BLOCKED','reason':'BASE_REPORT_HASH_MISMATCH'}); continue
        out=(args.out_root/cid/'oracle-interpretation.json').resolve(); out.parent.mkdir(parents=True,exist_ok=True)
        if out.exists(): results.append({'candidate_id':cid,'status':'BLOCKED','reason':'ORACLE_OUTPUT_EXISTS'}); continue
        argv=[sys.executable,str(interpreter.resolve()),'--admission-row',entry['admission_only_ref'],'--base-run',str(report),'--upstream-root',str(args.upstream_root.resolve()),'--out',str(out)]
        proc=subprocess.run(argv,text=True,capture_output=True,check=False)
        if not out.is_file(): results.append({'candidate_id':cid,'status':'BLOCKED','reason':'ORACLE_OUTPUT_MISSING','returncode':proc.returncode,'stderr':proc.stderr.strip()}); continue
        payload=load(out); results.append({'candidate_id':cid,'status':'RECORDED','classification':payload.get('classification'),'returncode':proc.returncode,'oracle_ref':str(out),'oracle_sha256':sha256_file(out)})
    batch={'schema_id':'ndv-p1-s2-oracle-batch-receipt-v1','status':'ORACLE_BATCH_RECORDED','execution_receipt_ref':str(args.execution_receipt.resolve()),'execution_receipt_sha256':sha256_file(args.execution_receipt.resolve()),'execution_plan_ref':str(args.execution_plan.resolve()),'execution_plan_sha256':sha256_file(args.execution_plan.resolve()),'interpreter_ref':str(interpreter.resolve()),'interpreter_sha256':sha256_file(interpreter.resolve()),'upstream_root':str(args.upstream_root.resolve()),'results':results,'model_execution':'NONE','treatment_execution':'NOT_EXECUTED','holdout_access':'NONE','completed_at':datetime.now(timezone.utc).isoformat()}
    args.receipt.parent.mkdir(parents=True,exist_ok=True)
    if args.receipt.exists(): raise SystemExit(f'refusing overwrite: {args.receipt}')
    args.receipt.write_text(json.dumps(batch,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps({'status':batch['status'],'receipt':str(args.receipt),'classifications':[{'candidate_id':r.get('candidate_id'),'classification':r.get('classification'),'status':r.get('status')} for r in results]},indent=2)); return 0 if all(r.get('status')=='RECORDED' for r in results) else 2
if __name__=='__main__': raise SystemExit(main())
