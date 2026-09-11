"""Run-replay proof helper. Usage: python scripts/replay_check.py --run-id N"""
import argparse, os, sys
from pathlib import Path
REPO_ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(REPO_ROOT/'etl'/'src')); os.chdir(REPO_ROOT)
from replay import replay_run
p=argparse.ArgumentParser(); p.add_argument('--run-id',type=int,required=True); p.add_argument('--source',default='sales'); a=p.parse_args(); print(replay_run(a.run_id,a.source))
