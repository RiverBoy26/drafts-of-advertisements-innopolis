import json, re, hashlib
from pathlib import Path
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import FeatureUnion, Pipeline

ROOT=Path(__file__).resolve().parents[1]
CLASS_IDS=(102,103,104,105,106)
SELECTED_THRESHOLD=0.45 # fixed threshold retained across five near-duplicate grouped folds
SEED=42
def norm(s):return re.sub(r"\s+"," ",s.lower().replace("ё","е")).strip()
rows=[json.loads(x) for x in (ROOT/"data/public-train-annotated.jsonl").read_text(encoding="utf8").splitlines() if x.strip()]
dedup={}
for r in rows:dedup.setdefault(norm(r["description"]),r)
rows=list(dedup.values()); X=[norm(r["description"]) for r in rows]
Y=[[int(mc in {int(y["mcId"]) for y in r.get("found_microcategories",[])}) for mc in CLASS_IDS] for r in rows]
model=Pipeline([("features",TfidfVectorizer(analyzer="char_wb",ngram_range=(3,5),min_df=2,max_features=350000,sublinear_tf=True)),("clf",OneVsRestClassifier(LogisticRegression(C=200,max_iter=800,class_weight="balanced",random_state=SEED,solver="liblinear")))])
model.fit(X,Y)
(ROOT/"artifacts").mkdir(exist_ok=True)
joblib.dump({"model":model,"class_ids":CLASS_IDS,"input_field":"description","threshold":SELECTED_THRESHOLD,"training_seed":SEED,"threshold_selection":"fixed 0.45; five near-duplicate grouped validation splits, cosine threshold .95; organizer weak labels","version":"tfidf-charwb-35-c200-min2-v2"},ROOT/"artifacts/cpu_char.joblib",compress=3)
normalized_source=(ROOT/"data/public-train-annotated.jsonl").read_bytes().replace(b"\r\n",b"\n")
print(json.dumps({"source_rows":10000,"fit_rows":len(rows),"unique_normalized_descriptions":len(set(X)),"sha256_input_lf_normalized":hashlib.sha256(normalized_source).hexdigest(),"seed":SEED,"class_ids":CLASS_IDS,"threshold":SELECTED_THRESHOLD,"analyzer":"char_wb","ngram_range":[3,5],"min_df":2,"max_features":350000,"actual_feature_count":len(model.named_steps["features"].vocabulary_),"C":200,"solver":"liblinear","artifact":"artifacts/cpu_char.joblib","label_source":"organizer weak labels; not gold","validation":"five separate near-duplicate grouped splits"},ensure_ascii=False))
