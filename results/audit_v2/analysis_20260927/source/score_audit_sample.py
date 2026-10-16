"""Score all main audit texts with a pinned, cached BERT model, offline."""
import argparse
import json
import os
from pathlib import Path
import tempfile
from audit_common import MODEL, MAX_TOKENS, digest, text_hash, validate_package

def atomic_json(path,value):
    path=Path(path)
    if path.exists():
        raise FileExistsError(f'Refusing to overwrite {path.name}')
    fd,tmp=tempfile.mkstemp(prefix='.incomplete-',dir=path.parent)
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:
            json.dump(value,f,indent=2)
        # Hard-link publication is atomic and refuses an existing destination.
        os.link(tmp,path)
    finally:
        os.unlink(tmp)

def score(run):
    run=Path(run); destination=run/'_hidden_predictions.json'
    if destination.exists():
        raise FileExistsError('Predictions already exist; no files changed')
    manifest,sheets,key=validate_package(run)
    import torch
    import transformers
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    revision=manifest['model_revision']
    tok=AutoTokenizer.from_pretrained(MODEL,revision=revision,local_files_only=True)
    model=AutoModelForSequenceClassification.from_pretrained(MODEL,revision=revision,local_files_only=True)
    model.eval(); torch.set_num_threads(min(4,torch.get_num_threads()))
    if [model.config.id2label[i] for i in range(5)]!=['1 star','2 stars','3 stars','4 stars','5 stars']:
        raise ValueError('Unexpected BERT label mapping')
    main=sheets['labelling_sheet.csv']; byid={r['item_id']:r for r in key}
    order=sorted(main,key=lambda r:len(r['review_text'])); predictions={}
    with torch.inference_mode():
        for start in range(0,len(order),16):
            batch=order[start:start+16]
            enc=tok([r['review_text'] for r in batch],padding=True,truncation=True,max_length=MAX_TOKENS,return_tensors='pt')
            probs=torch.softmax(model(**enc).logits,dim=1).tolist()
            for row,p in zip(batch,probs):
                stars=max(range(5),key=lambda i:p[i])+1
                comp=float(byid[row['item_id']]['vader_compound'])
                predictions[row['item_id']]=dict(text_sha256=text_hash(row['review_text']),bert_probabilities=p,
                    bert_label='negative' if stars<=2 else 'neutral' if stars==3 else 'positive',
                    bert_forced='positive' if p[3]+p[4]>=p[0]+p[1] else 'negative',
                    vader_label='positive' if comp>=0.05 else 'negative' if comp<=-0.05 else 'neutral')
            print(f'Scored {min(start+16,len(order))}/{len(order)}',flush=True)
    atomic_json(destination,dict(model=MODEL,model_revision=revision,max_tokens=MAX_TOKENS,
        torch_version=torch.__version__,transformers_version=transformers.__version__,
        manifest_sha256=digest(run/'_hidden_manifest.json'),predictions=predictions))

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('run',type=Path)
    score(parser.parse_args().run)
