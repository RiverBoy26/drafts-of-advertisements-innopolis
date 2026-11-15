"""Retrain the existing CPU half with original data plus authored trap candidates."""
import json,time
from pathlib import Path
import joblib,numpy as np
from benchmark_user_updated_cpu import ROOT,IDS,SEEDS,make,norm,rows

EXTRA_REPEAT=8
def extras():
 raw=[json.loads(s) for s in (ROOT/'data/human_style_trap_candidates.jsonl').read_text(encoding='utf8').splitlines() if s.strip()]
 texts=[norm(r['description']) for r in raw]
 y=np.asarray([[int(i in {v['mcId'] for v in r['found_microcategories']}) for i in IDS] for r in raw],dtype=np.uint8)
 return texts,y
def main():
 _,texts,y=rows();extra,ey=extras()
 assert len(extra)==60 and not (set(texts)&set(extra))
 base=json.loads((ROOT/'work/user_updated_cpu_predictions.json').read_text(encoding='utf8'))
 ood=[json.loads(s)['description'] for s in (ROOT/'data/user-updated-ood.jsonl').read_text(encoding='utf8').splitlines() if s.strip()]
 saved={};path=ROOT/'work/human_traps_cpu_predictions.json'
 for seed in SEEDS:
  b=base[str(seed)];tr=b['train_indices'];va=b['val_indices']
  train_texts=[texts[i] for i in tr]+extra*EXTRA_REPEAT
  train_y=np.vstack((y[tr],np.tile(ey,(EXTRA_REPEAT,1))))
  model=make(seed);t=time.perf_counter();model.fit(train_texts,train_y)
  saved[str(seed)]={'val_indices':va,'y':y[va].tolist(),'scores':model.predict_proba([texts[i] for i in va]).tolist(),
                    'ood_scores':model.predict_proba(ood).tolist(),'fit_seconds':round(time.perf_counter()-t,1)}
  path.write_text(json.dumps(saved),encoding='utf8')
  print(json.dumps({'seed':seed,'fit_seconds':saved[str(seed)]['fit_seconds']}),flush=True)
 model=make(42);t=time.perf_counter();model.fit(texts+extra*EXTRA_REPEAT,np.vstack((y,np.tile(ey,(EXTRA_REPEAT,1)))))
 out=ROOT/'artifacts/cpu_char_human_traps.joblib';joblib.dump({'model':model,'class_ids':IDS,'input_field':'description',
       'threshold':.475,'version':'user-updated-plus-human-traps-v1','training_rows_unique_base':len(texts),
       'authored_trap_rows':len(extra),'authored_repeat':EXTRA_REPEAT},out,compress=3)
 print(json.dumps({'artifact':str(out),'final_fit_seconds':round(time.perf_counter()-t,1)}),flush=True)
if __name__=='__main__':main()
