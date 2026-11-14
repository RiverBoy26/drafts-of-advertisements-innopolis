import json, re, hashlib
from pathlib import Path
import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import FeatureUnion, Pipeline

ROOT=Path(__file__).resolve().parents[1]
CLASS_IDS=(102,103,104,105,106)
SELECTED_THRESHOLD=0.45 # char-only threshold selected on near-duplicate grouped validation (seed 42)
SEED=42
def norm(s):return re.sub(r"\s+"," ",s.lower().replace("ё","е")).strip()
rows=[json.loads(x) for x in (ROOT/"data/public-train-annotated.jsonl").read_text(encoding="utf8").splitlines() if x.strip()]
dedup={}
for r in rows:dedup.setdefault(norm(r["description"]),r)
rows=list(dedup.values()); X=[norm(r["description"]) for r in rows]
Y=[[int(mc in {int(y["mcId"]) for y in r.get("found_microcategories",[])}) for mc in CLASS_IDS] for r in rows]
model=Pipeline([("features",TfidfVectorizer(analyzer="char",ngram_range=(3,5),max_features=150000,sublinear_tf=True)),("clf",OneVsRestClassifier(LogisticRegression(C=4,max_iter=300,class_weight="balanced",random_state=SEED)))])
model.fit(X,Y)
(ROOT/"artifacts").mkdir(exist_ok=True)
joblib.dump({"model":model,"class_ids":CLASS_IDS,"input_field":"description","threshold":SELECTED_THRESHOLD,"training_seed":SEED,"threshold_selection":"near-duplicate clustered validation on organizer weak labels; seed 42; cosine threshold .95","version":"tfidf-char-v1"},ROOT/"artifacts/cpu_char.joblib",compress=3)
print(json.dumps({"source_rows":10000,"fit_rows":len(rows),"unique_normalized_descriptions":len(set(X)),"sha256_input":hashlib.sha256((ROOT/"data/public-train-annotated.jsonl").read_bytes()).hexdigest(),"seed":SEED,"class_ids":CLASS_IDS,"threshold":SELECTED_THRESHOLD,"artifact":"artifacts/cpu_char.joblib","label_source":"organizer weak labels; not gold","validation":"separate grouped evaluator"},ensure_ascii=False))
