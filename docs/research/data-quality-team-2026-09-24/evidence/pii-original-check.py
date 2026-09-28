import json,pathlib,ast
from datasets import load_dataset
rr=[json.loads(l) for p in pathlib.Path('dataset/release/v1.1-ai/build').glob('F5.*.jsonl') for l in p.read_text().splitlines()];lookup={r['provenance']['source_id']:r for r in rr if r['provenance']['source']=='ai4privacy'}
seen=[];bad=[];spanbad=[];target=[]
for x in load_dataset('ai4privacy/pii-masking-300k',revision='c8c77895a005822682b66ab547fc0422579bc1d3',split='validation',streaming=True):
 sid=str(x['id'])
 if sid not in lookup:continue
 r=lookup[sid];sp=ast.literal_eval(x['privacy_mask']) if isinstance(x['privacy_mask'],str) else x['privacy_mask'];seen.append(sid)
 if x['source_text']!=r['state']['text'] or len(sp)!=len(r['spans']):bad.append(r['id'])
 for a,b in zip(sp,r['spans']):
  if (int(a['start']),int(a['end']),a['label'].upper())!=(b['start'],b['end'],b['source_label']):spanbad.append(r['id'])
 if sid in ('47929C','49869H','50937E','44145A') or sid[:-1] in ('50846','51890','53180'):target.append(x)
 if len(seen)==len(lookup):break
pathlib.Path('/tmp/gold-pii-fidelity.json').write_text(json.dumps({'checked':len(seen),'bad':bad,'spanbad':spanbad,'verified_target_ids':[r['id'] for r in target]},indent=2));print(len(seen),bad,spanbad,flush=True)
