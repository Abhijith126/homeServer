"""Check that DNS health requires answers and authenticated recursion."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DNSHealthTests(unittest.TestCase):
    def run_health(self, root_status='NOERROR', root_flags='qr rd ra ad', pihole_status='NOERROR'):
        with tempfile.TemporaryDirectory() as tmp:
            dig = Path(tmp) / 'dig'
            dig.write_text('''#!/usr/bin/env bash
if [[ "$*" == *5335* ]]; then
    printf ';; ->>HEADER<<- opcode: QUERY, status: %s, id: 1\\n;; flags: %s; QUERY: 1, ANSWER: 1\\n' "$ROOT_STATUS" "$ROOT_FLAGS"
else
    printf ';; ->>HEADER<<- opcode: QUERY, status: %s, id: 1\\n' "$PIHOLE_STATUS"
fi
exit 0
''')
            dig.chmod(0o755)
            env = dict(os.environ, PATH=tmp + ':' + os.environ['PATH'], ROOT_STATUS=root_status,
                       ROOT_FLAGS=root_flags, PIHOLE_STATUS=pihole_status)
            return subprocess.run(['bash', str(ROOT / 'stacks/infra/pihole-unbound/dns-healthcheck.sh')],
                                  env=env, capture_output=True).returncode

    def test_authenticated_recursion_and_forwarding_pass(self):
        self.assertEqual(self.run_health(), 0)

    def test_servfail_is_rejected_even_when_dig_exits_zero(self):
        self.assertNotEqual(self.run_health(root_status='SERVFAIL'), 0)
        self.assertNotEqual(self.run_health(pihole_status='SERVFAIL'), 0)

    def test_unauthenticated_response_is_rejected(self):
        self.assertNotEqual(self.run_health(root_flags='qr rd ra'), 0)


if __name__ == '__main__':
    unittest.main()
