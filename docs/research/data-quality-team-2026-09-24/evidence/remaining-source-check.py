import json,pathlib
from goldrails_dataset.sources import jbb_artifacts,jailbreakbench,ailuminate_demo
rs=[json.loads(l) for p in pathlib.Path('dataset/release/v1.1-ai/build').glob('F[12].*.jsonl') for l in p.read_text().splitlines()]
out={}
for mod in [jbb_artifacts,jailbreakbench,ailuminate_demo]:
 orig={r.id:r for r in mod.load()};rr=[r for r in rs if r['provenance']['source']==mod.NAME];bad=[r['id'] for r in rr if r['id'] not in orig or r['state']['text']!=orig[r['id']].state.text or r['expected']!=orig[r['id']].expected];out[mod.NAME]={'checked':len(rr),'mismatches':bad};print(out,flush=True)
pathlib.Path('/tmp/gold-rest-fidelity.json').write_text(json.dumps(out,indent=2))
