#!/usr/bin/env python3
"""Create an atomic config archive; restart only containers we stopped."""
import argparse
from datetime import datetime, timezone
import importlib.util
import os
from pathlib import Path
import signal
import subprocess
import tempfile

spec = importlib.util.spec_from_file_location('bootstrap_config', Path(__file__).with_name('bootstrap-config.py'))
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


def backup(stack_dir, stop=False):
    stack_dir = Path(stack_dir).resolve()
    settings = dict(os.environ, **config.read_env(stack_dir / '.env'))
    for key in ('DOCKER_DATA', 'NFS_BACKUP'):
        if not settings.get(key) or not Path(settings[key]).is_absolute():
            raise ValueError(f'{key} must be an absolute configured path')
    source = Path(settings['DOCKER_DATA']) / stack_dir.name
    if not source.is_dir():
        raise ValueError(f'No data directory: {source}')
    destination = Path(settings['NFS_BACKUP']) / stack_dir.name
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / (stack_dir.name + '-' + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S%f') + '.tar.gz')
    fd, temporary = tempfile.mkstemp(prefix='.backup-', suffix='.partial', dir=destination)
    os.close(fd)
    running = []
    try:
        if stop:
            running = subprocess.check_output(
                ['docker', 'compose', 'ps', '-q', '--status', 'running'], cwd=stack_dir, text=True).split()
            if running:
                subprocess.run(['docker', 'stop', *running], check=True)
        subprocess.run(['tar', '-czf', temporary, '-C', str(source.parent), source.name], check=True)
        subprocess.run(['tar', '-tzf', temporary], check=True, stdout=subprocess.DEVNULL)
        os.replace(temporary, archive)
    finally:
        Path(temporary).unlink(missing_ok=True)
        if running:
            subprocess.run(['docker', 'start', *running], check=True)
    for old in sorted(destination.glob(stack_dir.name + '-*.tar.gz'), reverse=True)[7:]:
        old.unlink()
    print(f'Backup complete: {archive}')
    return archive


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stack_dir', type=Path)
    parser.add_argument('--stop', action='store_true')
    args = parser.parse_args()
    def interrupted(signum, frame):
        raise KeyboardInterrupt(f'Interrupted by signal {signum}')
    signal.signal(signal.SIGTERM, interrupted)
    backup(args.stack_dir, args.stop)
