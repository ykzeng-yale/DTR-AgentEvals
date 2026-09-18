#!/usr/bin/env python3
import argparse,json
from pathlib import Path
from dtr_agent_evals.local_pilot import run
p=argparse.ArgumentParser();p.add_argument("--config",default="configs/local_pilot.json");p.add_argument("--output",default="results/local_pilot")
a=p.parse_args();run(json.loads(Path(a.config).read_text()),a.output)
