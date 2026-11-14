"""CV of exact 50/50 CPU+RuBERT ensemble, with and without CPU noise negatives."""
import json, time
from pathlib import Path
import numpy as np
from sklearn.metrics import f1_score,precision_score,recall_score
from sklearn.neighbors import NearestNeighbors
from scipy.sparse.csgraph import connected_components
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import GroupShuffleSplit
from benchmark_noise_robustness import ROOT,IDS,SEEDS,load,OOD
from benchmark_noise_training import noise_pool,make_model

def main():
 raw,texts,y=load(); gvec=TfidfVectorizer(analyzer='char',ngram_range=(3,5),min_df=2,max_features=100000,sublinear_tf=True); z=gvec.fit_transform(texts); graph=NearestNeighbors(radius=.05,metric='cosine',algorithm='brute',n_jobs=-1).fit(z).radius_neighbors_graph(z,mode='connectivity'); _,groups=connected_components(graph,directed=False)
 bert=json.loads(np.load(ROOT/'work/rubert_base_predictions.npz')['payload'].item()); cpu=json.loads(np.load(ROOT/'work/vocab_c200_predictions.npz')['payload'].item()); ck=ROOT/'work'/'ensemble_noise64_checkpoint.json'; foldrows=json.loads(ck.read_text(encoding='utf-8')) if ck.exists() else []; done={r['seed'] for r in foldrows}; t0=time.perf_counter()
 for seed in SEEDS:
  if seed in done: continue
  tr,va=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=seed).split(texts,y,groups)); b=bert[str(seed)]; assert b['val_indices']==va.tolist(); bs=np.asarray(b['scores_by_epoch']['3']); clean=cpu[f'{seed}|cap350k_min2_sublinear']; assert clean['indices']==va.tolist(); cs=np.asarray(clean['scores']); neg=noise_pool(64,seed); m=make_model(seed); m.fit([texts[i] for i in tr]+neg,np.vstack([y[tr],np.zeros((64,len(IDS)),dtype=np.uint8)])); ns=m.predict_proba([texts[i] for i in va]); ood=OOD+noise_pool(120,seed+10000); oscores=m.predict_proba(ood)
  foldrows.append({'seed':seed,'y':y[va].tolist(),'bert':bs.tolist(),'cpu_clean':cs.tolist(),'cpu_noise64':ns.tolist(),'ood_noise64':oscores.tolist(),'fit_seconds':round(time.perf_counter()-t0,1)}); ck.write_text(json.dumps(foldrows),encoding='utf-8'); print(json.dumps({'seed':seed,'rows':len(va)}),flush=True)
 out=[]
 for r in foldrows:
  yv=np.asarray(r['y']); b=np.asarray(r['bert']); cc=np.asarray(r['cpu_clean']); nn=np.asarray(r['cpu_noise64']); oo=np.asarray(r['ood_noise64'])
  for name,s,o in [('original_ensemble',.5*b+.5*cc,None),('noise64_cpu_ensemble',.5*b+.5*nn,oo)]:
   for th in (.45,.475,.50,.525,.55,.575,.60):
    p=s>=th; row={'seed':r['seed'],'model':name,'threshold':th,'micro_f1':float(f1_score(yv,p,average='micro',zero_division=0)),'precision':float(precision_score(yv,p,average='micro',zero_division=0)),'recall':float(recall_score(yv,p,average='micro',zero_division=0))}
    if o is not None:
     q=o>=th; row.update(ood_fpr_any=float(q.any(1).mean()),ood_mean_labels=float(q.sum(1).mean()))
    out.append(row)
 summary=[]
 for name in ('original_ensemble','noise64_cpu_ensemble'):
  for th in (.45,.475,.50,.525,.55,.575,.60):
   rr=[r for r in out if r['model']==name and r['threshold']==th]; keys=[k for k in rr[0] if k not in ('seed','model','threshold')]; summary.append({'model':name,'threshold':th,**{k:float(np.mean([r[k] for r in rr])) for k in keys}})
 report={'weighting':'exact 50/50 old RuBERT CV probabilities + CPU CV probabilities','noise64_cpu':'CPU trained per fold with 64 all-zero synthetic negatives; RuBERT same clean fold checkpoint','split':'same five grouped 80/20 seeds, assertions confirm identical validation order','summary':summary,'folds':out,'latency_scope':'not yet end-to-end ensemble latency; excludes batching/model load'}; (ROOT.parent/'docs'/'ensemble_noise64_cv.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps({'summary':summary},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
