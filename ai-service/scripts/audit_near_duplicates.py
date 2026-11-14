import json,re,hashlib
from pathlib import Path
import numpy as np
from sklearn.model_selection import GroupShuffleSplit
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors
ROOT=Path(__file__).resolve().parents[1]; seed=42
def norm(s):return re.sub(r"\s+"," ",s.lower().replace("ё","е")).strip()
raw=[json.loads(x) for x in (ROOT/"data/public-train-annotated.jsonl").read_text(encoding="utf8").splitlines() if x.strip()]
uniq=list({norm(x["description"]):norm(x["description"]) for x in raw}.values()); groups=np.asarray([hashlib.sha256(x.encode()).hexdigest() for x in uniq]); tr,va=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=seed).split(uniq,groups=groups))
vec=TfidfVectorizer(analyzer="char",ngram_range=(3,5),min_df=2,max_features=100000,sublinear_tf=True); matrix=vec.fit_transform(uniq)
nn=NearestNeighbors(n_neighbors=1,metric="cosine",algorithm="brute",n_jobs=-1).fit(matrix[tr]); dist,_=nn.kneighbors(matrix[va]); sim=1-dist.ravel()
print(json.dumps({"split_seed":seed,"unique_descriptions":len(uniq),"train_groups":len(tr),"validation_groups":len(va),"max_similarity":float(sim.max()),"mean_max_similarity":float(sim.mean()),"validation_groups_with_train_near_duplicate_ge_0_90":int((sim>=.90).sum()),"share_ge_0_90":float((sim>=.90).mean()),"validation_groups_with_train_near_duplicate_ge_0_95":int((sim>=.95).sum()),"method":"character TF-IDF 3-5grams, cosine nearest train description"},indent=2))
