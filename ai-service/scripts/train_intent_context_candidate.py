"""Train a candidate on independent, label-controlled intent contrasts."""
import argparse, json, random, time
from pathlib import Path

import joblib
import numpy as np
import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from benchmark_user_updated_cpu import ROOT, IDS, make, rows, norm
from train_human_traps_cpu import extras

SEED = 42
HUMAN_REPEAT = 8
INTENT_REPEAT = 4

def supplemental():
    items=[json.loads(x) for x in (ROOT/'data/intent_context_augmented.jsonl').read_text(encoding='utf8').splitlines() if x.strip()]
    texts=[norm(x['description']) for x in items]
    labels=np.asarray([[int(c in {v['mcId'] for v in x['found_microcategories']}) for c in IDS] for x in items],dtype=np.uint8)
    return texts,labels

class Data(Dataset):
    def __init__(self,encoded,labels):self.encoded=encoded;self.labels=labels
    def __len__(self):return len(self.labels)
    def __getitem__(self,i):
        return {**{k:v[i] for k,v in self.encoded.items()},'labels':torch.tensor(self.labels[i],dtype=torch.float32)}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--scope',action='store_true',help='Further fit using offer/mention scope contrasts')
    args=parser.parse_args()
    if not torch.cuda.is_available():raise RuntimeError('CUDA required for this candidate fit')
    random.seed(SEED);np.random.seed(SEED);torch.manual_seed(SEED);torch.cuda.manual_seed_all(SEED);torch.set_num_threads(4)
    _,base,by=rows();human,hy=extras();intent,iy=supplemental()
    assert not (set(base)&set(intent)) and not (set(human)&set(intent))
    texts=base+human*HUMAN_REPEAT+intent*INTENT_REPEAT
    labels=np.vstack((by,np.tile(hy,(HUMAN_REPEAT,1)),np.tile(iy,(INTENT_REPEAT,1))))
    if args.scope:
        scope_items=[json.loads(x) for x in (ROOT/'data/offer_scope_contrasts.jsonl').read_text(encoding='utf8').splitlines() if x.strip()]
        scope=[norm(x['description']) for x in scope_items]
        sy=np.asarray([[int(c in {v['mcId'] for v in x['found_microcategories']}) for c in IDS] for x in scope_items],dtype=np.uint8)
        assert not (set(base+human+intent)&set(scope))
        texts+=scope*4
        labels=np.vstack((labels,np.tile(sy,(4,1))))
    t=time.perf_counter();cpu=make(SEED);cpu.fit(texts,labels)
    cpu_file=ROOT/('artifacts/cpu_char_intent_scope.joblib' if args.scope else 'artifacts/cpu_char_intent_context.joblib')
    joblib.dump({'model':cpu,'class_ids':IDS,'input_field':'description','threshold':.525,'version':'intent-context-candidate','training_rows':len(texts)},cpu_file,compress=3)
    print(json.dumps({'cpu_fit_seconds':round(time.perf_counter()-t,1),'artifact':str(cpu_file)}),flush=True)
    old=ROOT/('artifacts/rubert_intent_context' if args.scope else 'artifacts/rubert_human_traps');tok=AutoTokenizer.from_pretrained(old,local_files_only=True)
    encoded=tok(texts,truncation=True,max_length=512,padding=False)
    def collate(batch):
        ys=torch.stack([x.pop('labels') for x in batch]);o=tok.pad(batch,padding=True,return_tensors='pt');o['labels']=ys;return o
    loader=DataLoader(Data(encoded,labels),batch_size=4,shuffle=True,collate_fn=collate,pin_memory=True)
    model=AutoModelForSequenceClassification.from_pretrained(old,local_files_only=True).cuda();opt=torch.optim.AdamW(model.parameters(),lr=3e-6 if args.scope else 5e-6,weight_decay=.01)
    scaler=torch.amp.GradScaler('cuda');t=time.perf_counter();opt.zero_grad(set_to_none=True);losses=[]
    for step,batch in enumerate(loader,1):
        batch={k:v.cuda(non_blocking=True) for k,v in batch.items()}
        with torch.amp.autocast('cuda',dtype=torch.float16):loss=model(**batch).loss/2
        scaler.scale(loss).backward()
        if step%2==0 or step==len(loader):
            scaler.unscale_(opt);torch.nn.utils.clip_grad_norm_(model.parameters(),1.0);scaler.step(opt);scaler.update();opt.zero_grad(set_to_none=True)
        losses.append(float(loss.detach())*2)
        if step%250==0:print(json.dumps({'step':step,'total':len(loader),'elapsed_seconds':round(time.perf_counter()-t,1),'mean_loss':round(float(np.mean(losses[-250:])),4)}),flush=True)
    out=ROOT/('artifacts/rubert_intent_scope' if args.scope else 'artifacts/rubert_intent_context');out.mkdir(exist_ok=True);model.save_pretrained(out,safe_serialization=True);tok.save_pretrained(out)
    print(json.dumps({'rubert_fit_seconds':round(time.perf_counter()-t,1),'artifact':str(out),'mean_loss':float(np.mean(losses)),'base_unique':len(base),'human_examples':len(human),'intent_examples':len(intent),'intent_repeat':INTENT_REPEAT,'scope_examples':len(scope) if args.scope else 0}),flush=True)

if __name__=='__main__':main()
