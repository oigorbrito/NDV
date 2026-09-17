#!/usr/bin/env python3
"""Apply explicit pre-treatment F1-F6 assignments to an S2 candidate evidence state.

Assignments are operator/research judgments based on frozen task statements and the
frozen historical taxonomy. This tool never consults treatment/model outcomes.
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

def apply(state_path:Path, assignments_path:Path, taxonomy_path:Path)->dict[str,Any]:
    state_path=require_file(state_path,'candidate state'); assignments_path=require_file(assignments_path,'family assignments'); taxonomy_path=require_file(taxonomy_path,'family taxonomy')
    state,assignments,taxonomy=load(state_path),load(assignments_path),load(taxonomy_path)
    if state.get('schema_id')!='ndv-p1-s2-candidate-evidence-state-v1': raise ValueError('candidate evidence state v1 required')
    if assignments.get('schema_id')!='ndv-p1-s2-family-assignments-v1': raise ValueError('family assignments v1 required')
    if taxonomy.get('schema_id')!='ndv-p1-s2-family-taxonomy-v1': raise ValueError('family taxonomy v1 required')
    for obj,name in ((state,'candidate state'),(assignments,'assignments'),(taxonomy,'taxonomy')):
        if obj.get('treatment_execution')!='NOT_EXECUTED' or obj.get('holdout_access')!='NONE': raise ValueError(f'{name} contaminated')
    if assignments.get('wave_id')!=state.get('wave_id'): raise ValueError('assignment wave mismatch')
    if assignments.get('candidate_state_sha256')!=sha256_file(state_path): raise ValueError('assignment/candidate-state hash mismatch')
    if assignments.get('taxonomy_sha256')!=sha256_file(taxonomy_path): raise ValueError('assignment/taxonomy hash mismatch')
    candidates=state.get('candidates'); records=assignments.get('assignments')
    if not isinstance(candidates,list) or not isinstance(records,list): raise ValueError('candidate/assignment arrays required')
    by_id={r.get('candidate_id'):r for r in records if isinstance(r,dict)}
    ids=[c.get('candidate_id') for c in candidates if isinstance(c,dict)]
    if len(by_id)!=len(records) or set(by_id)!=set(ids): raise ValueError('assignment set must exactly match candidate set')
    allowed=set(taxonomy.get('families',{})); out=[]
    for c in candidates:
        cid=c['candidate_id']; a=by_id[cid]; fam=a.get('family'); rationale=a.get('rationale')
        if fam not in allowed: raise ValueError(f'{cid}: invalid family {fam!r}')
        if a.get('task_statement_sha256')!=c.get('task_statement_sha256'): raise ValueError(f'{cid}: task statement hash mismatch')
        if not isinstance(rationale,str) or not rationale.strip(): raise ValueError(f'{cid}: non-empty rationale required')
        updated=dict(c); updated['proposed_family']=fam; updated['family_assignment']={'family':fam,'rationale':rationale.strip(),'task_statement_sha256':c.get('task_statement_sha256'),'taxonomy_ref':str(taxonomy_path),'taxonomy_sha256':sha256_file(taxonomy_path),'performance_based':False}; out.append(updated)
    return {'schema_id':'ndv-p1-s2-candidate-evidence-state-v2','wave_id':state.get('wave_id'),'wave_ref':state.get('wave_ref'),'wave_file_sha256':state.get('wave_file_sha256'),'source_candidate_state_ref':str(state_path),'source_candidate_state_sha256':sha256_file(state_path),'taxonomy_ref':str(taxonomy_path),'taxonomy_sha256':sha256_file(taxonomy_path),'assignments_ref':str(assignments_path),'assignments_sha256':sha256_file(assignments_path),'candidates':out,'treatment_execution':'NOT_EXECUTED','holdout_access':'NONE','built_at':datetime.now(timezone.utc).isoformat()}
def main()->int:
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--state',required=True,type=Path); ap.add_argument('--assignments',required=True,type=Path); ap.add_argument('--taxonomy',type=Path,default=Path('experiments/p1/s2-family-taxonomy-v1.json')); ap.add_argument('--out',type=Path,default=Path('.ndv-corpus/s2-w01/candidate-evidence-state-assigned.json')); args=ap.parse_args()
    try: result=apply(args.state,args.assignments,args.taxonomy)
    except (OSError,ValueError,json.JSONDecodeError) as exc: print(json.dumps({'status':'FAIL','reason':'FAMILY_ASSIGNMENT_BLOCKED','detail':str(exc)},indent=2)); return 2
    args.out.parent.mkdir(parents=True,exist_ok=True)
    if args.out.exists(): raise SystemExit(f'refusing overwrite: {args.out}')
    args.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps({'status':'FAMILY_ASSIGNMENTS_APPLIED','out':str(args.out),'candidate_count':len(result['candidates'])},indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
