#!/usr/bin/env python3
"""Build a derived S2 candidate evidence state from frozen wave + quarantine.

The frozen discovery wave is never mutated. This state promotes only byte-verified
quarantine facts needed by admission tooling. Family remains unassigned until a
separate task-statement-based assignment step. No treatment/model/holdout access.
"""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

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

def build(wave_path:Path, materialization_receipt:Path)->dict[str,Any]:
    wave_path=require_file(wave_path,'wave'); materialization_receipt=require_file(materialization_receipt,'materialization receipt'); wave,receipt=load(wave_path),load(materialization_receipt)
    if wave.get('schema_id')!='ndv-p1-s2-candidate-wave-v1': raise ValueError('unexpected wave schema')
    if receipt.get('schema_id')!='ndv-p1-s2-wave-materialization-receipt-v2' or receipt.get('status')!='MATERIALIZED_QUARANTINED': raise ValueError('materialization receipt v2/pass required')
    if receipt.get('wave_id')!=wave.get('wave_id') or receipt.get('wave_file_sha256')!=sha256_file(wave_path): raise ValueError('materialization/wave binding mismatch')
    if receipt.get('treatment_execution')!='NOT_EXECUTED' or receipt.get('holdout_access')!='NONE' or receipt.get('model_execution')!='NONE': raise ValueError('materialization contamination')
    aggregate_path=require_file(Path(receipt['quarantine_aggregate_ref']),'quarantine aggregate')
    if receipt.get('quarantine_aggregate_file_sha256')!=sha256_file(aggregate_path): raise ValueError('quarantine aggregate hash mismatch')
    aggregate=load(aggregate_path); manifests=aggregate.get('manifests'); candidates=wave.get('candidates')
    if aggregate.get('schema_id')!='ndv-p1-s2-quarantine-aggregate-v2' or aggregate.get('wave_id')!=wave.get('wave_id') or not isinstance(manifests,list) or not isinstance(candidates,list): raise ValueError('invalid quarantine aggregate')
    by_id={m.get('candidate_id'):m for m in manifests if isinstance(m,dict)}
    if set(by_id)!={c.get('candidate_id') for c in candidates}: raise ValueError('candidate/quarantine set mismatch')
    out=[]
    for c in candidates:
        cid=c['candidate_id']; m=by_id[cid]
        if m.get('status')!='PASS' or m.get('treatment_execution')!='NOT_EXECUTED' or m.get('holdout_access')!='NONE': raise ValueError(f'{cid}: quarantine not clean/pass')
        admission=require_file(Path(m['admission_only_ref']),f'{cid} admission-only'); executor=require_file(Path(m['executor_visible_ref']),f'{cid} executor-visible'); a,e=load(admission),load(executor)
        if a.get('candidate_id')!=cid or e.get('candidate_id')!=cid: raise ValueError(f'{cid}: artifact identity mismatch')
        source=a.get('source') or {}; binding=e.get('source_binding') or {}
        for field,val in [('source_row_index',c.get('source_row_index')),('source_instance_id',c.get('source_instance_id'))]:
            if source.get(field)!=val: raise ValueError(f'{cid}: admission {field} mismatch')
        raw=m.get('ndv_canonical_row_sha256'); task=m.get('task_statement_sha256'); projection=m.get('executor_visible_sha256')
        if source.get('ndv_canonical_row_sha256')!=raw or binding.get('ndv_canonical_row_sha256')!=raw or e.get('task_statement_sha256')!=task or e.get('executor_visible_sha256')!=projection: raise ValueError(f'{cid}: quarantine hash binding mismatch')
        out.append({
            'candidate_id':cid,'source_id':wave.get('source',{}).get('source_id'),'source_instance_id':c.get('source_instance_id'),'source_row_index':c.get('source_row_index'),'repository':c.get('repository'),'base_revision':c.get('base_revision'),'language':c.get('language'),'image_ref':c.get('image_ref'),'task_statement_ref':c.get('task_statement_ref'),
            'task_statement_sha256':task,'ndv_canonical_row_sha256':raw,'executor_visible_sha256':projection,
            'quarantine_manifest_ref':m.get('manifest_ref') or m.get('quarantine_manifest_ref'),'admission_only_ref':str(admission),'executor_visible_ref':str(executor),
            'quarantine_status':'PASS','solution_isolation':'PROVEN','solution_isolation_basis':'STRICT_EXECUTOR_VISIBLE_ALLOWLIST_AND_QUARANTINE_PASS',
            'proposed_family':'UNASSIGNED_PENDING_SCREEN','family_assignment':None,'disposition':'SCREENING','treatment_execution':'NOT_EXECUTED','holdout_access':'NONE'
        })
    return {'schema_id':'ndv-p1-s2-candidate-evidence-state-v1','wave_id':wave.get('wave_id'),'wave_ref':str(wave_path),'wave_file_sha256':sha256_file(wave_path),'materialization_receipt_ref':str(materialization_receipt),'materialization_receipt_sha256':sha256_file(materialization_receipt),'candidates':out,'treatment_execution':'NOT_EXECUTED','holdout_access':'NONE','built_at':datetime.now(timezone.utc).isoformat()}
def main()->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--wave',type=Path,default=Path('experiments/p1/s2-candidate-wave-01.json')); ap.add_argument('--materialization-receipt',required=True,type=Path); ap.add_argument('--out',type=Path,default=Path('.ndv-corpus/s2-w01/candidate-evidence-state.json')); args=ap.parse_args()
    try: result=build(args.wave,args.materialization_receipt)
    except (OSError,ValueError,json.JSONDecodeError) as exc: print(json.dumps({'status':'FAIL','reason':'CANDIDATE_STATE_BLOCKED','detail':str(exc)},indent=2)); return 2
    args.out.parent.mkdir(parents=True,exist_ok=True)
    if args.out.exists(): raise SystemExit(f'refusing overwrite: {args.out}')
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps({'status':'CANDIDATE_STATE_READY','out':str(args.out),'candidate_count':len(result['candidates'])},indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
