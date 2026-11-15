"""Grouped evaluation and final CPU fitting for the user-supplied updated labels."""
import json, hashlib, re, time
from pathlib import Path
import joblib
import numpy as np
from scipy.sparse.csgraph import connected_components
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.neighbors import NearestNeighbors
from sklearn.multiclass import OneVsRestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

ROOT=Path(__file__).resolve().parents[1]; IDS=(102,103,104,105,106); SEEDS=(42,7,21,101,2026)
def norm(s):return re.sub(r'\s+',' ',s.lower().replace('ё','е')).strip()
def rows():
 raw=[json.loads(s) for s in (ROOT/'data/user-updated-train.jsonl').read_text(encoding='utf8').splitlines() if s.strip()]
 dedup={}
 for x in raw:dedup.setdefault(norm(x['description']),x)
 texts=list(dedup); y=np.asarray([[int(c in {int(z['mcId']) for z in dedup[t].get('found_microcategories',[])}) for c in IDS] for t in texts],dtype=np.uint8)
 return raw,texts,y
def make(seed):return Pipeline([('tfidf',TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),min_df=2,max_features=350000,sublinear_tf=True)),('clf',OneVsRestClassifier(LogisticRegression(C=200,max_iter=800,class_weight='balanced',random_state=seed,solver='liblinear')))])
def main():
 raw,texts,y=rows(); ood=[json.loads(s)['description'] for s in (ROOT/'data/user-updated-ood.jsonl').read_text(encoding='utf8').splitlines() if s.strip()]
 graph=TfidfVectorizer(analyzer='char',ngram_range=(3,5),min_df=2,max_features=100000,sublinear_tf=True).fit_transform(texts)
 neighbors=NearestNeighbors(radius=.05,metric='cosine',algorithm='brute',n_jobs=-1).fit(graph).radius_neighbors_graph(graph,mode='connectivity')
 n_components,groups=connected_components(neighbors,directed=False)
 saved={}; metrics=[]; work=ROOT/'work'; work.mkdir(exist_ok=True)
 for seed in SEEDS:
  tr,va=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=seed).split(texts,y,groups)); model=make(seed); start=time.perf_counter(); model.fit([texts[i] for i in tr],y[tr]); fit=time.perf_counter()-start
  scores=model.predict_proba([texts[i] for i in va]); ood_scores=model.predict_proba(ood)
  saved[str(seed)]={'train_indices':tr.tolist(),'val_indices':va.tolist(),'y':y[va].tolist(),'scores':scores.tolist(),'ood_scores':ood_scores.tolist(),'fit_seconds':fit}
  for threshold in (.35,.4,.45,.475,.5,.525,.55,.575,.6):
   p=scores>=threshold; q=ood_scores>=threshold
   metrics.append({'seed':seed,'threshold':threshold,'micro_f1':float(f1_score(y[va],p,average='micro',zero_division=0)),'precision':float(precision_score(y[va],p,average='micro',zero_division=0)),'recall':float(recall_score(y[va],p,average='micro',zero_division=0)),'ood_fpr_any':float(q.any(axis=1).mean())})
  (work/'user_updated_cpu_predictions.json').write_text(json.dumps(saved),encoding='utf8');print(json.dumps({'seed':seed,'train':len(tr),'val':len(va),'fit_seconds':round(fit,1)}),flush=True)
 final=make(42);t=time.perf_counter(); final.fit(texts,y);final_fit=time.perf_counter()-t
 out=ROOT/'artifacts/cpu_char_user_updated.joblib';out.parent.mkdir(exist_ok=True);joblib.dump({'model':final,'class_ids':IDS,'input_field':'description','threshold':.475,'version':'user-updated-cpu-v1','training_rows':len(texts)},out,compress=3)
 report={'source_sha256':hashlib.sha256((ROOT/'data/user-updated-train.jsonl').read_bytes()).hexdigest(),'ood_sha256':hashlib.sha256((ROOT/'data/user-updated-ood.jsonl').read_bytes()).hexdigest(),'source_rows':len(raw),'unique_train_texts':len(texts),'ood_rows':len(ood),'near_duplicate_components':int(n_components),'seeds':SEEDS,'split':'5 repeated 80/20 GroupShuffleSplit folds over near-duplicate components cosine >=0.95','metrics':metrics,'cpu_final_fit_seconds':final_fit,'cpu_artifact':str(out)}
 (work/'user_updated_cpu_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps({'saved':str(out),'final_fit_seconds':round(final_fit,1),'metrics_at_045':[r for r in metrics if r['threshold']==.45]},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
