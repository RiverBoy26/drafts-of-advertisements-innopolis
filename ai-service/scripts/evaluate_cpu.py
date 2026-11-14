import json, re, hashlib
from pathlib import Path
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import Pipeline
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import f1_score, precision_score, recall_score
from sklearn.neighbors import NearestNeighbors
from scipy.sparse.csgraph import connected_components
ROOT=Path(__file__).resolve().parents[1]; IDS=(102,103,104,105,106); SEED=42
def norm(s):return re.sub(r"\s+"," ",s.lower().replace("ё","е")).strip()
raw=[json.loads(line) for line in (ROOT/"data/public-train-annotated.jsonl").read_text(encoding="utf8").splitlines() if line.strip()]
dedup={}
for r in raw:dedup.setdefault(norm(r["description"]),r)
rows=list(dedup.values()); X=[norm(r["description"]) for r in rows]; exact_groups=np.asarray([hashlib.sha256(x.encode()).hexdigest() for x in X]); Y=np.asarray([[int(c in {int(z["mcId"]) for z in r.get("found_microcategories",[])}) for c in IDS] for r in rows])
near_vec=TfidfVectorizer(analyzer="char",ngram_range=(3,5),min_df=2,max_features=100000,sublinear_tf=True); near_matrix=near_vec.fit_transform(X)
near_graph=NearestNeighbors(radius=.05,metric="cosine",algorithm="brute",n_jobs=-1).fit(near_matrix).radius_neighbors_graph(near_matrix,mode="connectivity")
n_components,near_groups=connected_components(near_graph,directed=False)
tr,va=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=SEED).split(X,Y,near_groups))
cross_nn=NearestNeighbors(n_neighbors=1,metric="cosine",algorithm="brute",n_jobs=-1).fit(near_matrix[tr]); cross_max=1-cross_nn.kneighbors(near_matrix[va],return_distance=True)[0].ravel()
reports=[]
for name,vec in [("word",TfidfVectorizer(ngram_range=(1,2),max_features=100000,sublinear_tf=True)),("char",TfidfVectorizer(analyzer="char",ngram_range=(3,5),max_features=150000,sublinear_tf=True)),("word_char",None)]:
 if name=="word_char":
  from sklearn.pipeline import FeatureUnion
  vector=FeatureUnion([("word",TfidfVectorizer(ngram_range=(1,2),max_features=80000,sublinear_tf=True)),("char",TfidfVectorizer(analyzer="char",ngram_range=(3,5),max_features=120000,sublinear_tf=True))])
 else:vector=vec
 pipe=Pipeline([("tfidf",vector),("ovr",OneVsRestClassifier(LogisticRegression(C=4,max_iter=300,class_weight="balanced",random_state=SEED)))])
 pipe.fit([X[i] for i in tr],Y[tr]); scores=pipe.predict_proba([X[i] for i in va]); choices=[]
 for threshold in (.15,.2,.25,.3,.35,.4,.45,.5):
  pred=(scores>=threshold).astype(int); choices.append((f1_score(Y[va],pred,average="micro",zero_division=0),threshold,pred))
 f1,threshold,pred=max(choices,key=lambda x:(x[0],-x[1]))
 reports.append({"model":name,"micro_f1":f1,"precision_micro":precision_score(Y[va],pred,average="micro",zero_division=0),"recall_micro":recall_score(Y[va],pred,average="micro",zero_division=0),"threshold_selected_on_validation":threshold})
print(json.dumps({"dataset":"organizer public-train-annotated.jsonl","label_quality":"weak automatic labels, not gold","source_rows":len(raw),"unique_description_groups":len(set(exact_groups)),"duplicate_rows_removed_before_split":len(raw)-len(rows),"near_duplicate_threshold_cosine":.95,"near_duplicate_components":int(n_components),"largest_component_size":int(np.bincount(near_groups).max()),"train_rows":len(tr),"validation_rows":len(va),"split":"GroupShuffleSplit on connected components of char-TFIDF pairs with cosine >= 0.95; exact duplicate descriptions deduplicated","seed":SEED,"nearest_cross_split_similarity":{"max":float(cross_max.max()),"count_ge_0_90":int((cross_max>=.90).sum()),"count_ge_0_95":int((cross_max>=.95).sum())},"metrics":reports},ensure_ascii=False,indent=2))
