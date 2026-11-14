import json,hashlib,time,statistics
from pathlib import Path
import numpy as np,pandas as pd,joblib
from sklearn.metrics import f1_score,precision_score,recall_score
ROOT=Path(__file__).resolve().parents[1]; IDS=(102,103,104,105,106); map_prefix={"stukaturn":102,"plitocn":103,"santehn":104,"elektrika":105,"pokleika oboev":106}
import sys;sys.path.insert(0,str(ROOT));from app.main import latin
def normalize(s):return " ".join(str(s).lower().replace(chr(0x451),"e").split())
def targets(labels):
    out=set()
    for label in labels:
        x=latin(normalize(label))
        for prefix,mc in map_prefix.items():
            if x.startswith(prefix):out.add(mc)
    return out
def main():
    data=pd.read_parquet(ROOT/"data/public-test-dataset.parquet"); train=[json.loads(x) for x in (ROOT/"data/public-train-annotated.jsonl").read_text(encoding="utf8").splitlines() if x.strip()]
    train_text={normalize(x["description"]) for x in train}; texts=[normalize(x) for x in data.description]; model_data=joblib.load(ROOT/"artifacts/cpu_char.joblib"); clf=model_data["model"]; classes=model_data["class_ids"]; threshold=model_data["threshold"]
    y=np.asarray([[int(c in targets(labels)) for c in IDS] for labels in data.categories]); pred=[]; lat=[]
    for text in data.description:
        t=time.perf_counter(); p=clf.predict_proba([normalize(text)])[0]; lat.append((time.perf_counter()-t)*1000); pred.append([int(c in set(classes[j] for j,x in enumerate(p) if x>=threshold)) for c in IDS])
    pred=np.asarray(pred); groups=len(set(texts)); overlaps=sum(x in train_text for x in texts)
    print(json.dumps({"dataset":"organizer public-test-dataset.parquet","source_mcId":101,"source_mcId_note":"assumption: file has no source mcId column","rows":len(data),"unique_normalized_descriptions":groups,"duplicate_rows":len(data)-groups,"exact_overlap_rows_with_train":overlaps,"threshold_from_training_artifact":threshold,"labels":"organizer public categories; inspect mapping; not blind evaluation","micro_f1":f1_score(y,pred,average="micro",zero_division=0),"precision_micro":precision_score(y,pred,average="micro",zero_division=0),"recall_micro":recall_score(y,pred,average="micro",zero_division=0),"per_class_f1":{str(c):f1_score(y[:,i],pred[:,i],zero_division=0) for i,c in enumerate(IDS)},"classification_latency_ms":{"p50":statistics.median(lat),"p95":sorted(lat)[int(.95*(len(lat)-1))]},"note":"Transparent public benchmark. It has been examined in earlier diagnostic passes; no threshold was selected on it. Do not treat as blind."},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
