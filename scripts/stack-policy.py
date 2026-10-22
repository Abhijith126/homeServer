#!/usr/bin/env python3
"""Shared optional-stack selection for old and new deployment entry points."""
import argparse
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bootstrap_config', ROOT / 'scripts/bootstrap-config.py')
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


def effective_skip(root, skipped):
    skipped = set(skipped)
    settings = config.read_env(Path(root) / '.env')
    if not config.usable(settings.get('BESZEL_AGENT_KEY', '').strip()):
        skipped.add('beszel-agent')
    return skipped


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip', default='')
    args = parser.parse_args()
    requested = set(args.skip.split())
    skipped = effective_skip(ROOT, requested)
    if 'beszel-agent' in skipped - requested:
        print('SKIP beszel-agent (no configured root BESZEL_AGENT_KEY; existing containers are left untouched)', file=sys.stderr)
    print(' '.join(sorted(skipped)))
