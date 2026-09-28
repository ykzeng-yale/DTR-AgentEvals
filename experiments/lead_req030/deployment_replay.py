import hashlib,json
from pathlib import Path
import transformers
from transformers import AutoTokenizer
root=Path('../req030-coder32-deploy-20260928-c').resolve()
tok=AutoTokenizer.from_pretrained(str(root/'model'),local_files_only=True,trust_remote_code=False)
rows=[]
for i in (1,2):
 b=json.loads((root/f'binding_{i}.json').read_text());r=json.loads((root/f'response_{i}.json').read_text())
 text=tok.apply_chat_template(b['messages'],tokenize=False,add_generation_prompt=True)
 assert text==b['rendered'];assert tok(text,add_special_tokens=False)['input_ids']==b['input_ids']
 assert tok.decode(r['output_ids'],skip_special_tokens=False)==r['raw']
 rows.append({'call':i,'input_tokens':len(b['input_ids']),'output_tokens':len(r['output_ids']),'exact_replay':True})
source=Path(transformers.__file__).parent/'models/qwen2/modeling_qwen2.py'
s=source.read_text();lines=s.splitlines(); excerpts=[]
for i,l in enumerate(lines):
 if 'Sliding Window Attention is enabled' in l or 'use_sliding_window' in l:
  excerpts.append({'line':i+1,'text':'\n'.join(lines[max(0,i-3):i+5])})
config=json.loads((root/'model/config.json').read_text())
Path('replay.json').write_text(json.dumps({'bindings':rows,'transformers':transformers.__version__,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'use_sliding_window':config['use_sliding_window'],'excerpts':excerpts},indent=2)+'\n')
