"""Test reporting without sending email or contacting Docker."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('report', ROOT / 'scripts/deploy-report.py')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


class ReportTests(unittest.TestCase):
    def test_detects_same_tag_image_update_and_container_recreation(self):
        old = {'app': {'container': 'one', 'image': 'app:1', 'digest': 'sha256:old'}}
        new = {'app': {'container': 'two', 'image': 'app:1', 'digest': 'sha256:new'}}
        self.assertIn('sha256:old', report.changes(old, new)[0])
        self.assertEqual(report.changes(old, old), [])

    def test_starttls_before_login_and_no_plaintext_mode(self):
        settings = dict(SMTP_HOST='smtp.example.invalid', SMTP_PORT='587', SMTP_USERNAME='user',
                        SMTP_PASSWORD='test-secret', SMTP_FROM='from@example.invalid', SMTP_TO='to@example.invalid')
        with patch.object(report.smtplib, 'SMTP') as smtp:
            self.assertEqual(report.send(settings, 'Subject', 'Body', '<table><tr><td>Body</td></tr></table>'), 'sent')
            calls = [call[0] for call in smtp.return_value.__enter__.return_value.method_calls]
            self.assertLess(calls.index('starttls'), calls.index('login'))
            self.assertIn('send_message', calls)
            message = smtp.return_value.__enter__.return_value.send_message.call_args.args[0]
            self.assertEqual(message.get_content_type(), 'multipart/alternative')
            self.assertEqual([part.get_content_type() for part in message.iter_parts()], ['text/plain', 'text/html'])
        with self.assertRaises(ValueError):
            report.send(dict(settings, SMTP_SECURITY='none'), 'Subject', 'Body')

    def test_html_tables_versions_recreation_timezone_and_escaping(self):
        old = {'container': 'one', 'image': 'registry:5000/app:v1@sha256:old', 'digest': 'sha256:old'}
        updated = dict(old, container='two', image='registry:5000/app:v2@sha256:new', digest='sha256:new')
        data = {'node': 'apps', 'host': '<script>host</script>', 'exit_code': 0,
                'started': '2026-10-02T22:24:27+00:00', 'finished': '2026-10-02T22:26:45+00:00',
                'revision': 'b030010471842160d48b805ee6304b6ee65eaefe',
                'before': {'homarr': old, 'bazarr': old},
                'after': {'homarr': updated, 'bazarr': dict(old, container='two')},
                'failures': [], 'step': '', 'free_after': 13904956620,
                'cleanup_by_phase': {'before': '0B', 'after': '373.7MB'}}
        text, html = report.render_email(data)
        self.assertIn('1 updated, 1 recreated', html)
        self.assertIn('03 Oct 2026, 00:24:27 CEST', html)
        self.assertIn('2m 18s', html)
        self.assertIn('homarr | Updated | v1 | v2', text)
        self.assertIn('bazarr | Recreated | v1 | v1', text)
        self.assertIn('&lt;script&gt;', html)
        self.assertNotIn('<script>', html)
        self.assertNotIn('registry:5000', html)
        self.assertIn('373.7MB', html)
        self.assertIn('<th scope="col"', html)
        data.update(exit_code=1, failures=['pull <error>'])
        _, html = report.render_email(data, 'Unknown/Zone')
        self.assertIn('Failed', html)
        self.assertIn('pull &lt;error&gt;', html)
        self.assertIn('UTC', html)
        self.assertEqual(report.change_rows({}, {'new': old})[0][1], 'Added')
        self.assertEqual(report.change_rows({'old': old}, {})[0][1], 'Removed')

    def test_quiet_run_and_failed_run_history(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(report, 'snapshot', return_value={}), \
                patch.object(report, 'free_space', return_value=1024), \
                patch.object(report, 'command', return_value='revision'), \
                patch.object(report.config, 'read_env', return_value={}), \
                patch.object(report, 'send') as send:
            directory = Path(tmp)
            report.begin('apps', directory)
            report.finish('apps', directory, 0)
            send.assert_not_called()
            report.begin('apps', directory)
            (directory / 'step').write_text('Git sync')
            send.side_effect = RuntimeError('secret must never enter history')
            report.finish('apps', directory, 1)
            send.assert_called_once()
            history = sorted((directory / 'history').glob('*.json'))
            data = json.loads(history[-1].read_text())
            self.assertEqual(data['notification'], 'failed: RuntimeError')
            self.assertNotIn('secret must never', history[-1].read_text())
            self.assertEqual(history[-1].stat().st_mode & 0o777, 0o600)
            self.assertEqual(data['exit_code'], 1)


if __name__ == '__main__':
    unittest.main()
