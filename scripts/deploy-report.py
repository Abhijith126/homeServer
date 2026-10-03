#!/usr/bin/env python3
"""Bounded deployment history and optional SMTP summaries; never email raw logs."""
import argparse
from datetime import datetime, timezone
from email.message import EmailMessage
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
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


def change_rows(before, after):
    if before is None or after is None:
        return []
    rows = []
    for name in sorted(before.keys() | after.keys()):
        old, new = before.get(name), after.get(name)
        if old == new:
            continue
        action = ('Added' if old is None else 'Removed' if new is None else
                  'Updated' if (old['image'], old['digest']) != (new['image'], new['digest']) else 'Recreated')
        rows.append((name, action, old, new))
    return rows


def image_version(value):
    if value is None:
        return '—'
    image = value['image'].split('@', 1)[0]
    last = image.rsplit('/', 1)[-1]
    return last.rsplit(':', 1)[1] if ':' in last else image


def render_email(report, timezone_name='Europe/Amsterdam'):
    """Email-safe inline styles, escaped values, and matching plain-text content."""
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        zone = ZoneInfo('UTC')
    started = datetime.fromisoformat(report['started'])
    finished = datetime.fromisoformat(report['finished'])
    seconds = max(0, int((finished - started).total_seconds()))
    duration = f'{seconds // 60}m {seconds % 60}s'
    failed = report['exit_code'] != 0
    result = 'Failed' if failed else 'Completed'
    rows = change_rows(report['before'], report['after'])
    counts = ', '.join(f'{sum(row[1] == action for row in rows)} {action.lower()}'
                       for action in ('Updated', 'Recreated', 'Added', 'Removed')
                       if any(row[1] == action for row in rows)) or 'No container changes'
    metadata = [('Node', report['node']), ('Host', report['host']), ('Result', result),
                ('Started', started.astimezone(zone).strftime('%d %b %Y, %H:%M:%S %Z')),
                ('Finished', finished.astimezone(zone).strftime('%d %b %Y, %H:%M:%S %Z')),
                ('Duration', duration), ('Git revision', report['revision'][:12])]
    cleanup = report.get('cleanup_by_phase', {})
    disk = [('Before deployment', cleanup.get('before', 'Unavailable')),
            ('After deployment', cleanup.get('after', 'Unavailable')),
            ('Docker disk free', f"{report['free_after'] / 1024**3:.2f} GiB"
             if report['free_after'] is not None else 'Unavailable')]
    failures = report['failures'] or ([report['step']] if failed else [])
    text = ['homeServer — Deployment ' + result, counts, '',
            *(f'{key}: {value}' for key, value in metadata), '',
            'App | Action | Previous version | Current version']
    text += [f'{name} | {action} | {image_version(old)} | {image_version(new)}'
             for name, action, old, new in rows]
    unavailable = report['before'] is None or report['after'] is None
    if unavailable:
        text.append('Container inventory unavailable; check the deployment journal.')
    text += ['', 'Storage cleanup', *(f'{key}: {value}' for key, value in disk), '',
             'Failed steps', *(failures or ['None']), '',
             'Recreated = container replaced with the same image.',
             'Details: journalctl -u homelab-deploy.service']

    def esc(value):
        return escape(str(value), quote=True)

    def table(headers, data):
        head = ''.join('<th scope="col" style="padding:10px;text-align:left;background:#edf2f7;'
                       'font-size:12px;color:#475569;border-bottom:1px solid #dbe3ec">' + esc(h) + '</th>' for h in headers)
        body = ''.join('<tr>' + ''.join('<td style="padding:10px;vertical-align:top;'
                       'border-bottom:1px solid #e2e8f0;overflow-wrap:anywhere">' + cell + '</td>' for cell in row)
                       + '</tr>' for row in data)
        return '<table width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;font-size:14px">' + '<thead><tr>' + head + '</tr></thead><tbody>' + body + '</tbody></table>'

    def version_cell(value, show_digest):
        cell = esc(image_version(value))
        if value and show_digest:
            cell += '<br><span style="font-size:11px;color:#64748b">' + esc(value['digest'][:19]) + '</span>'
        return cell

    app_rows = []
    for name, action, old, new in rows:
        show_digest = bool(old and new and old['digest'] != new['digest'])
        app_rows.append([esc(name), '<strong>' + esc(action) + '</strong>',
                        version_cell(old, show_digest), version_cell(new, show_digest)])
    accent = '#b91c1c' if failed else '#047857'
    html = ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"></head>'
            '<body style="margin:0;padding:20px 8px;background:#f1f5f9;font-family:Arial,Helvetica,sans-serif;color:#172033">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center">'
            '<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:720px;background:#ffffff;border:1px solid #e2e8f0">'
            '<tr><td style="padding:24px;background:#0f172a;color:#ffffff">'
            '<div style="font-size:12px;letter-spacing:2px;color:#cbd5e1">HOMESERVER</div>'
            '<h1 style="margin:10px 0;font-size:24px">' + esc(report['node']) + ' · Deployment report</h1>'
            '<div style="font-size:14px">' + esc(counts) + '</div></td></tr>'
            '<tr><td style="padding:24px"><p style="margin-top:0;font-weight:bold;color:' + accent + '">' + result + ' · ' + duration + '</p>'
            + table(['Run', 'Details'], [[esc(k), esc(v)] for k, v in metadata])
            + '<h2 style="font-size:18px;margin-top:28px">Container changes</h2>'
            + (table(['App', 'Action', 'Previous', 'Current'], app_rows) if app_rows else
               '<p>' + ('Container inventory unavailable; check the deployment journal.' if unavailable else 'No container changes.') + '</p>')
            + '<p style="font-size:12px;color:#64748b">Recreated means the container was replaced with the same image. Full image references remain in local history.</p>'
            + '<h2 style="font-size:18px;margin-top:28px">Storage cleanup</h2>'
            + table(['Metric', 'Value'], [[esc(k), esc(v)] for k, v in disk])
            + '<h2 style="font-size:18px;margin-top:28px">Failed steps</h2>'
            + (table(['Step'], [[esc(step)] for step in failures]) if failures else '<p style="color:#047857">None</p>')
            + '<p style="margin-top:28px;font-size:12px;color:#64748b">Logs on the node:<br>'
            '<code>journalctl -u homelab-deploy.service</code></p></td></tr></table></td></tr></table></body></html>')
    return '\n'.join(text), html


def send(settings, subject, body, html_body=None):
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
    if html_body is not None:
        message.add_alternative(html_body, subtype="html")
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
    report['cleanup_by_phase'] = {}
    for name in ('prune-before', 'prune-after'):
        report['cleanup'].extend(line for line in (directory / name).read_text().splitlines()
                                 if line.startswith('Total reclaimed space:'))
        totals = [line.split(':', 1)[1].strip() for line in (directory / name).read_text().splitlines()
                  if line.startswith('Total reclaimed space:')]
        if totals:
            report['cleanup_by_phase'][name.removeprefix('prune-')] = totals[-1]
    result = 'FAILED' if status else 'completed'
    report['notification'] = 'quiet: no container changes'
    history = directory / 'history'
    history.mkdir(exist_ok=True)
    target = history / (datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.json')
    save(target, report)
    if status or report['changes']:
        try:
            settings = config.read_env(ROOT / '.env')
            body, html_body = render_email(report, settings.get('TZ') or 'Europe/Amsterdam')
            report['notification'] = send(settings,
                f'[homeServer][{node}] Deployment {result}', body, html_body)
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
