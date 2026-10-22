"""Real firewall reapplication in a throwaway network namespace (Linux CI only)."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest


@unittest.skipUnless(sys.platform == 'linux' and os.geteuid() == 0 and shutil.which('unshare'),
                     'requires root in Linux CI; never changes the host network namespace')
class FirewallNamespaceTests(unittest.TestCase):
    def test_policy_reapplication_revokes_removed_allowlists(self):
        source = Path(__file__).resolve().parents[1] / 'scripts/docker-firewall.py'
        code = '''
import importlib.util, subprocess, sys
spec = importlib.util.spec_from_file_location('firewall', sys.argv[1])
firewall = importlib.util.module_from_spec(spec)
spec.loader.exec_module(firewall)
def run(*args):
    return subprocess.check_output(args, text=True)
for executable in ('iptables', 'ip6tables'):
    run(executable, '-N', 'DOCKER-USER')
    run(executable, '-N', 'UNRELATED')
    run(executable, '-A', 'UNRELATED', '-j', 'RETURN')
original = {'allowed_sources': ['192.0.2.0/24', '2001:db8::/64'], 'public_tcp': [8443]}
replacement = {'allowed_sources': ['198.51.100.0/24'], 'public_tcp': [443]}
firewall.install(original)
firewall.install(replacement)
once = {exe: run(exe, '-S') for exe in ('iptables', 'ip6tables')}
firewall.install(replacement)
for executable in ('iptables', 'ip6tables'):
    assert run(executable, '-S') == once[executable], 'Reapplication duplicated rules'
    chain = run(executable, '-S', 'HOMELAB-DOCKER')
    assert '192.0.2.0' not in chain and '2001:db8:' not in chain and '8443' not in chain
    assert '--ctorigdstport 443' in chain
    assert '-A UNRELATED -j RETURN' in run(executable, '-S', 'UNRELATED')
    assert run(executable, '-S', 'DOCKER-USER').count('-j HOMELAB-DOCKER') == 1
'''
        result = subprocess.run(['unshare', '--net', sys.executable, '-c', code, str(source)],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
