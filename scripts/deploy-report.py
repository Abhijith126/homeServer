#!/usr/bin/env python3
"""Bounded deployment history and optional SMTP summaries; never email raw logs."""
import argparse
from datetime import datetime, timezone
from email.message import EmailMessage
import importlib.util
import json
import os
from pathlib import Path
import shutil
import smtplib
import socket
import ssl
import subprocess
import sys
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bootstrap_config', ROOT / 'scripts/bootstrap-config.py')
config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(config)


def command(*args):
    return subprocess.check_output(args, cwd=ROOT, text=True, stderr=subprocess.DEVNULL, timeout=30).strip()


def snapshot(node):
    try:
        ids = command('docker', 'ps', '-aq', '--filter', 'label=homelab.node=' + node).split()
        if not ids:
            return {}
        fmt = '{{.Id}}\t{{.Name}}\t{{.Config.Image}}\t{{.Image}}'
        lines = command('docker', 'inspect', '--format', fmt, *ids).splitlines()
        result = {}
        for line in lines:
            ident, name, image, digest = line.split('\t')
            result[name.lstrip('/')] = {'container': ident, 'image': image, 'digest': digest}
        return result
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def free_space():
    try:
        path = command('docker', 'info', '--format', '{{.DockerRootDir}}')
        return shutil.disk_usage(path).free
    except (OSError, subprocess.SubprocessError):
        return None


def changes(before, after):
    if before is None or after is None:
        return ['Container inventory unavailable; check the deployment journal.']
    lines = []
    for name in sorted(before.keys() | after.keys()):
        old, new = before.get(name), after.get(name)
        if old == new:
            continue
        def describe(value):
            return 'absent' if value is None else value['image'] + ' [' + value['digest'][:19] + ']'
        lines.append(f'{name}: {describe(old)} -> {describe(new)}')
    return lines


def send(settings, subject, body):
    required = ('SMTP_HOST', 'SMTP_USERNAME', 'SMTP_PASSWORD', 'SMTP_FROM', 'SMTP_TO')
    if not all(settings.get(key) and settings[key] != 'CHANGEME' for key in required):
        return 'not configured'
    security = settings.get('SMTP_SECURITY', 'starttls')
    if security not in ('starttls', 'ssl'):
        raise ValueError('SMTP_SECURITY must be starttls or ssl')
    message = EmailMessage()
    message['Subject'] = subject
    message['From'] = settings['SMTP_FROM']
    message['To'] = settings['SMTP_TO']
    message.set_content(body)
    context = ssl.create_default_context()
    port = int(settings.get('SMTP_PORT') or ('465' if security == 'ssl' else '587'))
    client = smtplib.SMTP_SSL if security == 'ssl' else smtplib.SMTP
    options = {'timeout': 20}
    if security == 'ssl':
        options['context'] = context
    with client(settings['SMTP_HOST'], port, **options) as smtp:
        if security == 'starttls':
            smtp.ehlo()
            smtp.starttls(context=context)
            smtp.ehlo()
        smtp.login(settings['SMTP_USERNAME'], settings['SMTP_PASSWORD'])
        smtp.send_message(message)
    return 'sent'


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')
    path.chmod(0o600)


def begin(node, directory):
    directory.mkdir(parents=True, exist_ok=True)
    for name in ('step', 'failures', 'prune-before', 'prune-after'):
        (directory / name).write_text('')
    save(directory / 'report-active.json', {'started': datetime.now(timezone.utc).isoformat(),
         'node': node, 'host': socket.gethostname(), 'before': snapshot(node), 'free_before': free_space()})


def finish(node, directory, status):
    active = directory / 'report-active.json'
    if not active.exists():
        return
    report = json.loads(active.read_text())
    report.update(finished=datetime.now(timezone.utc).isoformat(), exit_code=status,
                  after=snapshot(node), free_after=free_space())
    report['changes'] = changes(report['before'], report['after'])
    report['step'] = (directory / 'step').read_text().strip()
    report['failures'] = (directory / 'failures').read_text().splitlines()
    try:
        report['revision'] = command('git', 'rev-parse', 'HEAD')
    except (OSError, subprocess.SubprocessError):
        report['revision'] = 'unavailable'
    report['cleanup'] = []
    for name in ('prune-before', 'prune-after'):
        report['cleanup'].extend(line for line in (directory / name).read_text().splitlines()
                                 if line.startswith('Total reclaimed space:'))
    result = 'FAILED' if status else 'completed'
    body = [f"Node: {node} ({report['host']})", f"Result: {result}",
            f"Started (UTC): {report['started']}", f"Finished (UTC): {report['finished']}",
            f"Git revision: {report['revision']}", '', 'Container changes:',
            *(report['changes'] or ['None']), '', 'Failed steps:',
            *(report['failures'] or ([report['step']] if status else ['None'])), '',
            'Cleanup (before/after):', *(report['cleanup'] or ['Unavailable'])]
    free = report['free_after']
    body += [f"Docker filesystem free: {free / 1024**3:.2f} GiB" if free is not None else 'Docker filesystem free: unavailable',
             '', 'Details: journalctl -u homelab-deploy.service']
    report['notification'] = 'quiet: no container changes'
    history = directory / 'history'
    history.mkdir(exist_ok=True)
    target = history / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.json')
    save(target, report)
    if status or report['changes']:
        try:
            report['notification'] = send(config.read_env(ROOT / '.env'),
                f'[homeServer][{node}] Deployment {result}', '\n'.join(body))
        except Exception as error:
            # SMTP errors may contain addresses or server responses; log type only.
            report['notification'] = 'failed: ' + type(error).__name__
        print('Deployment email: ' + report['notification'])
    save(target, report)
    for old in sorted(history.glob('*.json'), reverse=True)[50:]:
        old.unlink()
    active.unlink()


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('begin', 'finish'))
    parser.add_argument('node', choices=('apps', 'storage', 'infra'))
    parser.add_argument('--status', type=int, default=0)
    args = parser.parse_args()
    directory = ROOT / '.deploy-state' / args.node
    try:
        if args.action == 'begin':
            begin(args.node, directory)
        else:
            finish(args.node, directory, args.status)
    except Exception as error:
        print('Deployment reporting unavailable: ' + type(error).__name__)
