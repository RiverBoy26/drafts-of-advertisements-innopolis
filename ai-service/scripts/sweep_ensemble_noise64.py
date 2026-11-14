"""Sweep RuBERT/CPU probability weights and thresholds on grouped CV plus OOD."""
import json, time
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from sklearn.metrics import f1_score,precision_score,recall_score
from benchmark_noise_robustness import ROOT, OOD
from benchmark_noise_training import noise_pool
from app.transformer_classifier import RuBertClassifier

def main():
 folds=json.loads((ROOT/'work'/'ensemble_noise64_checkpoint.json').read_text(encoding='utf-8'))
 bert=RuBertClassifier(str(ROOT/'artifacts'/'rubert_base'))
 ood_sets=[OOD+noise_pool(120,int(r['seed'])+10000) for r in folds]
 bert_ood=[bert.predict_proba(x) for x in ood_sets]
 weights=(0,.1,.2,.3,.35,.375,.4,.425,.45,.475,.5,.525,.55,.575,.6,.625,.65,.675,.7,.8,.9,1.0); thresholds=(.35,.4,.425,.45,.475,.5,.525,.55,.575,.6,.625,.65)
 rows=[]
 for w in weights:
  for th in thresholds:
   vals=[]; oo=[]
   for r,bo in zip(folds,bert_ood):
    y=np.asarray(r['y']); c=np.asarray(r['cpu_noise64']); b=np.asarray(r['bert']); s=(1-w)*c+w*b; p=s>=th
    vals.append((f1_score(y,p,average='micro',zero_division=0),precision_score(y,p,average='micro',zero_division=0),recall_score(y,p,average='micro',zero_division=0)))
    so=np.asarray(r['ood_noise64']); o=(1-w)*so+w*bo; oo.extend((o>=th).any(axis=1).tolist())
   rows.append({'rubert_weight':w,'cpu_weight':1-w,'threshold':th,'micro_f1':float(np.mean([x[0] for x in vals])),'precision':float(np.mean([x[1] for x in vals])),'recall':float(np.mean([x[2] for x in vals])),'micro_f1_std':float(np.std([x[0] for x in vals])),'ood_fpr_any':float(np.mean(oo))})
 report={'setup':'Same 5 grouped 80/20 folds; CPU candidate trained with 64 synthetic negatives per fold; RuBERT unchanged. OOD includes 8 fixed traps + 120 generated negatives per fold. Weight sweep blends probabilities before thresholding.','rubert_weights':weights,'thresholds':thresholds,'rows':rows,'best_clean_f1':sorted(rows,key=lambda x:x['micro_f1'],reverse=True)[:20],'best_tradeoff':sorted(rows,key=lambda x:(x['micro_f1']-.5*x['ood_fpr_any']),reverse=True)[:20]}
 out=ROOT.parent/'docs'/'ensemble_sweep_noise64.json'; out.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8'); print(json.dumps({'saved':str(out),'best_clean_f1':report['best_clean_f1'][:8],'best_tradeoff':report['best_tradeoff'][:8]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
