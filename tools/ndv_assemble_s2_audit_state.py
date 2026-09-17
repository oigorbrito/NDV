#!/usr/bin/env python3
"""Assemble S2 audit-state from candidate/base/oracle/verifier evidence.

No execution occurs here. AUDIT_PASS is derived only from hash-valid evidence;
blocked/invalid evidence is represented explicitly rather than promoted manually.
"""
from __future__ import annotations
import argparse, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import ndv_build_s2_verifier_evidence as verifier

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
def index(items:Any,key='candidate_id')->dict[str,dict[str,Any]]:
    if not isinstance(items,list): raise ValueError('expected array')
    out={}
    for item in items:
        if not isinstance(item,dict) or not isinstance(item.get(key),str): raise ValueError(f'invalid {key}')
        if item[key] in out: raise ValueError(f'duplicate {key}: {item[key]}')
        out[item[key]]=item
    return out
def pure_digest(repo_digest:Any)->str|None:
    if not isinstance(repo_digest,str) or '@sha256:' not in repo_digest: return None
    return 'sha256:'+repo_digest.split('@sha256:',1)[1]
def write_json(path:Path,payload:dict[str,Any])->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists(): raise ValueError(f'refusing overwrite: {path}')
    path.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def main()->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--candidates',required=True,type=Path); ap.add_argument('--execution-plan',required=True,type=Path); ap.add_argument('--execution-receipt',required=True,type=Path); ap.add_argument('--oracle-receipt',required=True,type=Path); ap.add_argument('--verifier-receipt',required=True,type=Path); ap.add_argument('--environment-root',type=Path,default=Path('.ndv-corpus/s2-w01/environment')); ap.add_argument('--out',type=Path,default=Path('.ndv-corpus/s2-w01/audit-state.json')); args=ap.parse_args()
    try:
        cpath=require_file(args.candidates,'candidate state'); ppath=require_file(args.execution_plan,'execution plan'); erpath=require_file(args.execution_receipt,'execution receipt'); orpath=require_file(args.oracle_receipt,'oracle receipt'); vrpath=require_file(args.verifier_receipt,'verifier receipt')
        state,plan,execution,oracle_batch,verifier_batch=map(load,(cpath,ppath,erpath,orpath,vrpath))
        if state.get('schema_id')!='ndv-p1-s2-candidate-evidence-state-v2': raise ValueError('candidate evidence state v2 required')
        if plan.get('schema_id')!='ndv-p1-s2-base-audit-execution-plan-v1': raise ValueError('execution plan v1 required')
        if execution.get('schema_id')!='ndv-p1-s2-base-audit-execution-receipt-v1' or execution.get('plan_file_sha256')!=sha256_file(ppath): raise ValueError('execution receipt/plan mismatch')
        if oracle_batch.get('schema_id')!='ndv-p1-s2-oracle-batch-receipt-v1' or oracle_batch.get('execution_plan_sha256')!=sha256_file(ppath): raise ValueError('oracle receipt/plan mismatch')
        if verifier_batch.get('schema_id')!='ndv-p1-s2-verifier-batch-receipt-v1' or verifier_batch.get('execution_plan_sha256')!=sha256_file(ppath): raise ValueError('verifier receipt/plan mismatch')
        for obj,name in ((state,'candidate state'),(execution,'execution receipt'),(oracle_batch,'oracle receipt'),(verifier_batch,'verifier receipt')):
            if obj.get('treatment_execution')!='NOT_EXECUTED' or obj.get('holdout_access')!='NONE': raise ValueError(f'{name} contaminated')
    except (OSError,ValueError,json.JSONDecodeError) as exc:
        print(json.dumps({'status':'FAIL','reason':'AUDIT_STATE_BLOCKED','detail':str(exc)},indent=2)); return 2
    candidates=state['candidates']; base_idx=index(execution.get('results')); oracle_idx=index(oracle_batch.get('results')); verifier_idx=index(verifier_batch.get('results')); plan_idx=index(plan.get('entries')); audits=[]
    for c in candidates:
        cid=c['candidate_id']; base_rec=base_idx.get(cid,{}); oracle_rec=oracle_idx.get(cid,{}); ver_rec=verifier_idx.get(cid,{}); pe=plan_idx.get(cid,{})
        rec={'candidate_id':cid,'status':'ENVIRONMENT_BLOCKED','quarantine_status':c.get('quarantine_status'),'image_ref':c.get('image_ref'),'image_digest':None,'gold_patch_applied_in_base_mode':False,'test_patch_applied_in_base_mode':False,'harness_integrity':None,'base_run_ref':None,'base_run_sha256':None,'oracle_interpretation_ref':None,'oracle_interpretation_sha256':None,'oracle_classification':None,'base_behavior_matches_expected':None,'focal_verifier_ref':None,'focal_verifier_sha256':None,'preservation_ref':None,'preservation_sha256':None,'preservation_baseline_pass':None,'verifier_provenance_ref':None,'verifier_provenance_sha256':None,'verifier_independent':None,'environment_ref':None,'environment_sha256':None,'treatment_execution':'NOT_EXECUTED'}
        bref=base_rec.get('report_ref')
        if not isinstance(bref,str): audits.append(rec); continue
        bp=require_file(Path(bref),f'{cid} base report')
        if base_rec.get('report_sha256')!=sha256_file(bp): raise SystemExit(f'AUDIT_STATE_BLOCKED: {cid} base report hash mismatch')
        base=load(bp); rec['base_run_ref'],rec['base_run_sha256']=str(bp),sha256_file(bp); rec['harness_integrity']=base.get('harness_integrity'); rec['image_digest']=pure_digest(base.get('image_digest'))
        if base.get('status')=='ENVIRONMENT_BLOCKED' or base.get('harness_integrity')!='PASS': rec['status']='ENVIRONMENT_BLOCKED'; audits.append(rec); continue
        env={'schema_id':'ndv-p1-s2-environment-evidence-v1','candidate_id':cid,'repository':c.get('repository'),'base_revision':c.get('base_revision'),'image_ref':base.get('image_ref'),'repo_digest':base.get('image_digest'),'image_digest':rec['image_digest'],'runtime':base.get('runtime'),'network':base.get('network'),'workdir':base.get('workdir'),'test_commands_sha256':base.get('test_commands_sha256'),'runner_ref':plan.get('runner_ref'),'runner_sha256':plan.get('runner_file_sha256'),'base_run_ref':str(bp),'base_run_sha256':sha256_file(bp),'treatment_execution':'NOT_EXECUTED','holdout_access':'NONE'}
        env_path=(args.environment_root/cid/'environment-evidence.json').resolve(); write_json(env_path,env); rec['environment_ref'],rec['environment_sha256']=str(env_path),sha256_file(env_path)
        oref=oracle_rec.get('oracle_ref')
        if oracle_rec.get('status')!='RECORDED' or not isinstance(oref,str): rec['status']='ORACLE_BLOCKED'; audits.append(rec); continue
        op=require_file(Path(oref),f'{cid} oracle')
        if oracle_rec.get('oracle_sha256')!=sha256_file(op): raise SystemExit(f'AUDIT_STATE_BLOCKED: {cid} oracle hash mismatch')
        oracle=load(op); rec['oracle_interpretation_ref'],rec['oracle_interpretation_sha256']=str(op),sha256_file(op); rec['oracle_classification']=oracle.get('classification'); rec['base_behavior_matches_expected']=oracle.get('classification')=='EXPECTED_BASE_BEHAVIOR'
        if oracle.get('classification')!='EXPECTED_BASE_BEHAVIOR': rec['status']='ORACLE_BLOCKED'; audits.append(rec); continue
        bundle_ref=ver_rec.get('bundle_ref')
        if ver_rec.get('status')!='RECORDED' or not isinstance(bundle_ref,str): rec['status']='REJECTED'; audits.append(rec); continue
        bundle_path=require_file(Path(bundle_ref),f'{cid} verifier bundle')
        if ver_rec.get('bundle_file_sha256')!=sha256_file(bundle_path): raise SystemExit(f'AUDIT_STATE_BLOCKED: {cid} verifier bundle hash mismatch')
        bundle=load(bundle_path); root=bundle_path.parent; focal=require_file(Path(bundle['focal_ref']),f'{cid} focal'); preservation=require_file(Path(bundle['preservation_ref']),f'{cid} preservation'); provenance=require_file(Path(bundle['provenance_ref']),f'{cid} provenance'); fp,pp,prov=load(focal),load(preservation),load(provenance)
        if verifier.sha256(fp)!=bundle.get('focal_sha256') or verifier.sha256(pp)!=bundle.get('preservation_sha256') or verifier.sha256(prov)!=bundle.get('provenance_sha256'): raise SystemExit(f'AUDIT_STATE_BLOCKED: {cid} verifier canonical hash mismatch')
        rec.update({'focal_verifier_ref':str(focal),'focal_verifier_sha256':bundle['focal_sha256'],'preservation_ref':str(preservation),'preservation_sha256':bundle['preservation_sha256'],'verifier_provenance_ref':str(provenance),'verifier_provenance_sha256':bundle['provenance_sha256'],'verifier_independent':prov.get('independence',{}).get('frozen_before_treatment') is True and prov.get('independence',{}).get('derived_from_treatment_output') is False,'preservation_baseline_pass':all(x.get('observed')=='PASSED' for x in oracle.get('pass_to_pass',[])),'status':'AUDIT_PASS'})
        audits.append(rec)
    payload={'schema_id':'ndv-p1-s2-audit-state-v1','candidate_state_ref':str(cpath),'candidate_state_sha256':sha256_file(cpath),'wave_ref':state.get('wave_ref'),'audit_contract_ref':'experiments/p1/s2-verifier-environment-audit-v2.json','created_at':datetime.now(timezone.utc).isoformat(),'holdout_access':'NONE','audits':audits}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    if args.out.exists(): raise SystemExit(f'refusing overwrite: {args.out}')
    args.out.write_text(json.dumps(payload,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps({'status':'AUDIT_STATE_ASSEMBLED','out':str(args.out),'counts':{s:sum(a['status']==s for a in audits) for s in sorted(set(a['status'] for a in audits))}},indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
