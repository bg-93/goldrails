import json, pathlib, urllib.request, collections
from datasets import Dataset
root=pathlib.Path('dataset/release/v1.1-ai/build')
rows=[json.loads(l) for p in root.glob('F[1256].*.jsonl') for l in p.read_text().splitlines()]
out={}
cache=pathlib.Path.home()/'.cache/huggingface/datasets'
spec={'aegis2':('nvidia___aegis-ai-content-safety-dataset-2.0','test'),'openai_moderation':('mmathys___openai-moderation-api-evaluation','train'),'orbench':('bench-llm___or-bench','train'),'deepset_injections':('deepset___prompt-injections','train'),'gandalf':('Lakera___gandalf_ignore_instructions','train'),'ai4privacy':('ai4privacy___pii-masking-300k','validation')}
for name,(folder,split) in spec.items():
 ps=list((cache/folder).rglob('*-'+split+'.arrow'))
 if not ps: print(name,'MISSING CACHE',flush=True);continue
 ds=Dataset.from_file(str(ps[0])); src={str(x['id']):x for x in ds} if name in ('aegis2','ai4privacy') else dict(enumerate(ds))
 rr=[r for r in rows if r['provenance']['source']==name]; bad=[]
 for r in rr:
  sid=r['provenance']['source_id']; expected=r['expected']; text=r['state']['text']
  if name=='aegis2':
   sid,side=sid.rsplit(':',1);s=src[sid];ok=text==s[side] and expected==('yes' if s[side+'_label']=='unsafe' else 'no')
  elif name=='ai4privacy':
   s=src[sid];ok=text==s['source_text']
  else:
   s=src[int(sid)];field='prompt' if name in ('orbench','openai_moderation') else 'text';ok=text==s[field]
   if name=='deepset_injections':ok &= expected==('yes' if s['label']==1 else 'no')
   if name=='openai_moderation':ok &= expected==('yes' if any(str(s[c])=='1' for c in ('S','H','V','HR','SH','S3','H2','V2')) else 'no')
  if not ok:bad.append(r['id'])
 out[name]={'checked':len(rr),'mismatches':bad,'cache':str(ps[0])};print(name,len(rr),len(bad),flush=True)
base='https://raw.githubusercontent.com/ParticleMedia/RAGTruth/c103204b9ce28d6bbad859304bf30de72b8ed8fe/dataset/'
raw={f:[json.loads(l) for l in urllib.request.urlopen(base+f).read().decode().splitlines()] for f in ['source_info.jsonl','response.jsonl']}
# Raw publisher texts are not persisted by this audit script.
sources={s['source_id']:s for s in raw['source_info.jsonl']};responses={str(r['id']):r for r in raw['response.jsonl']};bad=[];invalid=[];implicit=[];qualities=collections.Counter()
rr=[r for r in rows if r['provenance']['source']=='ragtruth']
for r in rr:
 s=responses[r['provenance']['source_id']];orig=sources[s['source_id']]['source_info'];source=orig if isinstance(orig,str) else json.dumps(orig,ensure_ascii=False)
 if r['state']['text']!=s['response'] or r['state']['source']!=source or r['expected']!=('yes' if s['labels'] else 'no'):bad.append(r['id'])
 if any(not 0<=l['start']<l['end']<=len(s['response']) for l in s['labels']):invalid.append(r['id'])
 if any(l.get('implicit_true') for l in s['labels']):implicit.append(r['id'])
 qualities[s.get('quality')]+=1
out['ragtruth']={'checked':len(rr),'mismatches':bad,'invalid_spans':invalid,'implicit_true':implicit,'qualities':dict(qualities)}
print('ragtruth',out['ragtruth'],flush=True)
pathlib.Path('/tmp/gold-source-fidelity-counts.json').write_text(json.dumps(out,indent=2))
