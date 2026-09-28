"""Two frozen deployment probes. Outputs are data and are never executed."""
import hashlib
import json
import os
from pathlib import Path
import time
import torch
import transformers
import numpy as np
from transformers import AutoModelForCausalLM, AutoTokenizer


def save(name, value):
    Path(name).write_text(json.dumps(value, indent=2) + '\n')


def main():
    Path('inference.claim').open('x').close()
    assert np.__version__ == '1.26.4'
    assert torch.from_numpy(np.array([1., 2.], dtype=np.float32)).numpy().tolist() == [1., 2.]
    assert torch.__version__.split('+')[0] == '2.9.1'
    assert transformers.__version__ == '4.51.3'
    assert torch.version.cuda == '12.8' and torch.cuda.device_count() == 1
    meta = json.loads(Path('coder_model.json').read_text())
    # Recheck every model file, not just the preparation exit code.
    for e in meta['files']:
        h = hashlib.sha256()
        with (Path('model') / e['filename']).open('rb') as f:
            for data in iter(lambda: f.read(8*1024*1024), b''):
                h.update(data)
        assert h.hexdigest() == e['sha256'], e['filename']
    torch.manual_seed(20260928030)
    tokenizer = AutoTokenizer.from_pretrained('model', local_files_only=True, trust_remote_code=False)
    start = time.monotonic()
    model = AutoModelForCausalLM.from_pretrained('model', local_files_only=True,
        trust_remote_code=False, torch_dtype=torch.bfloat16, device_map={'': 0}, attn_implementation='sdpa')
    model.eval()
    save('load.json', {'seconds': time.monotonic()-start, 'model': meta['repo'], 'revision': meta['revision'],
         'torch': torch.__version__, 'transformers': transformers.__version__, 'cuda': torch.version.cuda,
         'gpu': torch.cuda.get_device_name(), 'job_id': os.environ['SLURM_JOB_ID']})
    requests = json.loads(Path('coder_requests.json').read_text())
    for i, messages in enumerate(requests, 1):
        rendered = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(rendered, add_special_tokens=False, return_tensors='pt').to('cuda')
        ids = inputs.input_ids[0].tolist()
        assert len(ids)+256 <= 32768
        save(f'binding_{i}.json', {'messages': messages, 'rendered': rendered, 'input_ids': ids,
             'rendered_sha256': hashlib.sha256(rendered.encode()).hexdigest()})
        started = time.monotonic()
        with torch.inference_mode():
            result = model.generate(**inputs, do_sample=False, max_new_tokens=256, use_cache=True,
                                    pad_token_id=tokenizer.eos_token_id)
        torch.cuda.synchronize()
        out = result[0, len(ids):].tolist()
        save(f'response_{i}.json', {'input_tokens':len(ids), 'output_tokens':len(out), 'output_ids':out,
             'raw':tokenizer.decode(out, skip_special_tokens=False), 'seconds':time.monotonic()-started,
             'peak_allocated_bytes':torch.cuda.max_memory_allocated(),
             'finish':'eos' if out and out[-1] == tokenizer.eos_token_id else 'length'})
    save('terminal.json', {'status':'completed', 'calls':2, 'kind':'deployment_only_not_task_competence'})

if __name__ == '__main__':
    main()
