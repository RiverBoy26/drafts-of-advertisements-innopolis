"""Create a separate copy of organizer train data with 64 synthetic hard negatives."""
import json
import argparse
from pathlib import Path
from benchmark_noise_robustness import ROOT, load
from benchmark_unseen_noise_families import gen_noise, TRAIN_TEMPLATES

def main():
 parser=argparse.ArgumentParser(); parser.add_argument('--count',type=int,default=64); count=parser.parse_args().count
 source=ROOT/'data'/'public-train-annotated.jsonl'; output=ROOT/'data'/f'public-train-annotated-noise{count}.jsonl'
 original=[json.loads(x) for x in source.read_text(encoding='utf-8').splitlines() if x.strip()]
 negatives=gen_noise(count,42,TRAIN_TEMPLATES)
 rows=original+[
  {'item_id':f'synthetic-noise-{i+1:04d}','title':'Синтетический отрицательный пример','description':text,
   'found_microcategories':[],'source_mcId':101,'synthetic_negative':True,'synthetic_kind':'OOD_or_non_offer'}
  for i,text in enumerate(negatives)]
 output.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows),encoding='utf-8')
 print(json.dumps({'source_rows':len(original),'synthetic_negative_rows':len(negatives),'output_rows':len(rows),'output':str(output)},ensure_ascii=False))
if __name__=='__main__':main()
