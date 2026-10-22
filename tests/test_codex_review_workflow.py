"""Exercise the comment workflow without contacting GitHub."""

import json
from pathlib import Path
import shutil
import subprocess
import textwrap
import unittest


WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/codex-review.yml'


@unittest.skipUnless(shutil.which('node'), 'Node.js is required')
class CodexReviewWorkflowTests(unittest.TestCase):
    def run_workflow(self, *, author='renovate[bot]', draft=False,
                     state='open', sha='abc', comments=None):
        source = WORKFLOW.read_text()
        script = textwrap.dedent(source.split('          script: |\n', 1)[1])
        pr = {'number': 41, 'user': {'login': author}, 'draft': draft,
              'state': state, 'head': {'sha': sha}}
        harness = '''
const pr = PR;
const comments = COMMENTS;
const created = [];
const context = {repo: {owner: 'owner', repo: 'repo'}, payload: {
  pull_request: {number: 41, head: {sha: 'abc'}}}};
const core = {info: () => {}};
const github = {rest: {
  pulls: {get: async () => ({data: pr})},
  issues: {listComments: () => {}, createComment: async args => created.push(args)}
}, paginate: async () => comments};
(async () => { SCRIPT })().then(() => console.log(JSON.stringify(created)))
  .catch(error => {console.error(error); process.exit(1);});
'''.replace('PR', json.dumps(pr)).replace('COMMENTS', json.dumps(comments or []))
        result = subprocess.run(['node', '-e', harness.replace('SCRIPT', script)],
                                check=True, capture_output=True, text=True)
        return json.loads(result.stdout)

    def test_requests_renovate_review(self):
        self.assertEqual(self.run_workflow()[0]['body'],
                         '@codex review\n\n<!-- codex-review-request -->')

    def test_skips_ineligible_prs(self):
        for kwargs in ({'author': 'someone'}, {'draft': True},
                       {'state': 'closed'}):
            with self.subTest(**kwargs):
                self.assertEqual(self.run_workflow(**kwargs), [])

    def test_deduplicates_bot_comment_across_revisions(self):
        comment = {'user': {'login': 'github-actions[bot]'},
                   'body': '<!-- codex-review-request -->'}
        self.assertEqual(self.run_workflow(comments=[comment]), [])
        self.assertEqual(self.run_workflow(sha='newer', comments=[comment]), [])
        comment['user']['login'] = 'someone'
        self.assertEqual(len(self.run_workflow(comments=[comment])), 1)

    def test_workflow_has_no_checkout_and_filters_author(self):
        source = WORKFLOW.read_text()
        self.assertNotIn('actions/checkout', source)
        self.assertIn("if: github.event.pull_request.user.login == 'renovate[bot]'", source)
        self.assertIn('pull-requests: write', source)
        self.assertIn('types: [opened]', source)
        for event in ('synchronize', 'reopened', 'ready_for_review'):
            self.assertNotIn(event, source)


if __name__ == '__main__':
    unittest.main()
