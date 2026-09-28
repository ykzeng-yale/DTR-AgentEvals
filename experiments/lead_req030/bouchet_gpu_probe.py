"""Bounded GPU runtime qualification; no model weights or task inference."""
import json
import os
import time
from pathlib import Path
import torch

assert torch.__version__.split('+')[0] == '2.9.1', torch.__version__
assert torch.version.cuda == '12.8', torch.version.cuda
assert torch.cuda.is_available()
assert torch.cuda.device_count() == 1
props = torch.cuda.get_device_properties(0)
torch.manual_seed(20260928)
a = torch.randn((1024, 1024), device='cuda', dtype=torch.bfloat16)
b = torch.randn_like(a)
start = time.monotonic()
c = a @ b
torch.cuda.synchronize()
assert torch.isfinite(c).all().item()
reference = a.float() @ b.float()
error = (c.float() - reference).norm() / reference.norm()
assert error.item() < .02, error.item()
result = dict(kind='infrastructure_only', job_id=os.environ['SLURM_JOB_ID'],
              torch=torch.__version__, cuda=torch.version.cuda, device=props.name,
              capability=list(torch.cuda.get_device_capability()),
              total_memory_bytes=props.total_memory, relative_error=error.item(),
              seconds=time.monotonic()-start, peak_bytes=torch.cuda.max_memory_allocated())
Path('result.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
