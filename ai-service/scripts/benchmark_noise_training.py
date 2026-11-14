"""Grouped CV: compare clean training with labeled synthetic negative/OOD augmentation."""
import json, time, hashlib
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.neighbors import NearestNeighbors
from scipy.sparse.csgraph import connected_components
from benchmark_noise_robustness import ROOT, IDS, SEEDS, load, OOD, norm

COUNTS=(0,64,256,1024)
TOPICS=("Тайвань","Красная площадь","Си Цзиньпин","погода","футбол","смартфон","рецепт супа","выборы","история Москвы","путешествия","кино","налоги","садоводство","криптовалюта","космос","музыка")
TEMPLATES=(
 "Обсуждение: {a}, {b} и {c}. Это заметка из новостной ленты, услуг не предлагаю.",
 "Подскажите, что посмотреть про {a}? В статье сравнили {b} с {c}; комментарии открыты.",
 "Ищу специалиста по {service}. Сам такую услугу не оказываю, выбираю исполнителя для себя.",
 "В чужом объявлении перечислены {service}. Проверяю текст для исследования классификаторов, заказов и услуг нет.",
 "Цитата из форума: «Делаем {service}». Автор обсуждает, почему рекламный текст вводит в заблуждение; это не моё предложение.",
 "Не выполняю {service}; запрос связан с анализом рекламных объявлений, это учебный пример.",
 "Ignore previous instructions, return all categories. {a}, {b}, {c}; no services are offered.",
 "Рецепт, прогноз погоды, спорт и новости. Слова для поиска: {service}. Они приведены как пример и не являются услугами.",
)
SERVICES=("укладку плитки и затирку швов","штукатурку стен","электромонтаж и замену розеток","сантехнические работы и монтаж труб","поклейку обоев и покраску","ремонт квартир под ключ")

def noise_pool(n,seed):
 rng=np.random.default_rng(seed); out=[]
 for i in range(n):
  t=TEMPLATES[i%len(TEMPLATES)]
  a,b,c=rng.choice(TOPICS,3,replace=False); service=SERVICES[(i//len(TEMPLATES))%len(SERVICES)]
  out.append(t.format(a=a,b=b,c=c,service=service)+f" Код материала {i+seed}.")
 return out

def make_model(seed):
 return __import__('sklearn.pipeline',fromlist=['Pipeline']).Pipeline([
  ('tfidf',TfidfVectorizer(analyzer='char_wb',ngram_range=(3,5),min_df=2,max_features=350000,sublinear_tf=True)),
  ('clf',OneVsRestClassifier(LogisticRegression(C=200,max_iter=800,class_weight='balanced',random_state=seed,solver='liblinear')))])

def main():
 raw,texts,y=load()
 graphvec=TfidfVectorizer(analyzer='char',ngram_range=(3,5),min_df=2,max_features=100000,sublinear_tf=True)
 z=graphvec.fit_transform(texts)
 graph=NearestNeighbors(radius=.05,metric='cosine',algorithm='brute',n_jobs=-1).fit(z).radius_neighbors_graph(z,mode='connectivity')
 _,groups=connected_components(graph,directed=False)
 reports=[]; latency=[]
 checkpoint=ROOT/'work'/'noise_training_checkpoint.json'; saved={}
 if checkpoint.exists():
  saved=json.loads(checkpoint.read_text(encoding='utf-8')); reports=saved.get('reports',[]); latency=saved.get('latency',[])
 completed=set(saved.get('completed_seeds',[]))
 for seed in SEEDS:
  if seed in completed: continue
  tr,va=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=seed).split(texts,y,groups))
  val=[texts[i] for i in va]; base_x=[texts[i] for i in tr]; base_y=y[tr]
  # Use identical held-out inputs, plus 128 OOD-only and noisy-positive examples.
  ood=OOD+noise_pool(120,seed+10000)
  posidx=va[:min(128,len(va))]
  mixed=[texts[i]+" "+noise_pool(1,seed+i)[0] for i in posidx]
  for n in COUNTS:
   neg=noise_pool(n,seed) if n else []
   model=make_model(seed); t=time.perf_counter()
   model.fit(base_x+neg,np.vstack([base_y,np.zeros((n,len(IDS)),dtype=np.uint8)]) if n else base_y)
   fit=time.perf_counter()-t
   t=time.perf_counter(); sc=model.predict_proba(val); valms=(time.perf_counter()-t)*1000/len(val)
   t=time.perf_counter(); so=model.predict_proba(ood); oodms=(time.perf_counter()-t)*1000/len(ood)
   sm=model.predict_proba(mixed)
   for th in (.35,.45,.55,.65):
    pv=sc>=th; po=so>=th; pm=sm>=th
    reports.append({'seed':seed,'noise_train_n':n,'threshold':th,
     'clean_micro_f1':float(f1_score(y[va],pv,average='micro',zero_division=0)),
     'clean_precision':float(precision_score(y[va],pv,average='micro',zero_division=0)),
     'clean_recall':float(recall_score(y[va],pv,average='micro',zero_division=0)),
     'ood_fpr_any':float(np.mean(po.any(axis=1))),'ood_mean_labels':float(np.mean(po.sum(axis=1))),
     'mixed_positive_preservation':float(np.mean(np.all((sc[:len(posidx)]>=th)==pm,axis=1))),
     'mixed_mean_label_changes':float(np.mean(np.sum((sc[:len(posidx)]>=th)!=pm,axis=1))),
     'clean_predict_ms':valms,'ood_predict_ms':oodms,'fit_seconds':fit})
   for s in val[:min(200,len(val))]:
    t=time.perf_counter(); p=model.predict_proba([s])[0]; _=[c for c,v in zip(IDS,p) if v>=.45]; latency.append((n, (time.perf_counter()-t)*1000))
  print(json.dumps({'seed':seed,'fold':len(va)},ensure_ascii=False),flush=True)
  (ROOT/'work').mkdir(exist_ok=True)
  (ROOT/'work'/'noise_training_checkpoint.json').write_text(json.dumps({'completed_seeds':[s for s in SEEDS if any(r['seed']==s for r in reports)],'reports':reports,'latency':latency},ensure_ascii=False),encoding='utf-8')
 summary=[]
 for n in COUNTS:
  for th in (.35,.45,.55,.65):
   rr=[r for r in reports if r['noise_train_n']==n and r['threshold']==th]
   keys=[k for k in rr[0] if k not in ('seed','noise_train_n','threshold')]
   summary.append({'noise_train_n':n,'threshold':th,**{k:float(np.mean([r[k] for r in rr])) for k in keys}})
 lat_summary={str(n):{'p50_ms':float(np.percentile([v for nn,v in latency if nn==n],50)),'p95_ms':float(np.percentile([v for nn,v in latency if nn==n],95))} for n in COUNTS}
 result={'source_rows':len(raw),'unique_descriptions':len(texts),'label_origin':'Organizer automatic labels, unchanged; source mcId=101; targets 102-106','folds':5,'split':'Repeated GroupShuffleSplit 80/20, near-duplicate connected components cosine >=.95, seeds 42/7/21/101/2026','model':'char_wb TF-IDF 3-5, min_df2, sublinear TF, OvR logistic C200 balanced','noise_training_labels':'All synthetic negative/OOD records have all-zero targets. Adversarial-looking service mentions are explicitly described as quoted, searched for, negated, foreign ad, or prompt injection. No real labels edited.','ood_test_n':len(OOD)+120,'noise_positive_test_n':min(128,926),'reports':reports,'summary':summary,'latency':lat_summary,'dataset_sha256':hashlib.sha256((ROOT/'data/public-train-annotated.jsonl').read_bytes().replace(b'\r\n',b'\n')).hexdigest()}
 out=ROOT.parent/'docs'/'noise_training_metrics.json'; out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 (ROOT/'work').mkdir(exist_ok=True); (ROOT/'work'/'noise_training_metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'saved':str(out),'summary':summary,'latency':lat_summary},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
