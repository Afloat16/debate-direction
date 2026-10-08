import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from debate_direction.cli import main
from debate_direction.config import SessionConfig
from debate_direction.demo import DEMO_QUESTION, DemoProvider
from debate_direction.engine import DebateEngine
from debate_direction.reports import render_html, render_markdown


def demo_report():
    report = DebateEngine(DemoProvider(), SessionConfig(model='demo-scripted', reasoning_effort='none', config_source='demo')).run(DEMO_QUESTION)
    report['demo'] = True
    return report


class ReportTests(unittest.TestCase):
    def test_full_public_proposal_versions_are_retained_as_separate_snapshots(self):
        report = demo_report()
        self.assertEqual([p['version'] for p in report['proposal_history']], [1, 2])
        self.assertEqual([p['recommended_option_id'] for p in report['proposal_history']], ['P1', 'P2'])
        self.assertTrue(all(p['reviewed'] for p in report['proposal_history']))
        self.assertEqual([r['reviewed_version'] for r in report['review_history']], [1, 2])
        report['proposal']['recommendation'] = 'changed by reader'
        self.assertNotEqual(report['proposal_history'][-1]['recommendation'], 'changed by reader')

    def test_report_escapes_active_markup_and_keeps_uncertainty(self):
        report = demo_report()
        injection = '<script>alert("key")</script><img src=x onerror=alert(1)>[go](javascript:alert(1))'
        report['question'] = injection
        report['proposal']['recommendation'] = injection
        html = render_html(report)
        markdown = render_markdown(report)
        self.assertNotIn('<script>', html)
        self.assertNotIn('<img src=x', html)
        self.assertIn('&lt;script&gt;', html)
        self.assertIn("default-src 'none'", html)
        self.assertNotIn('[go](javascript:', markdown)
        self.assertIn('尚未实际核验', html)
        self.assertIn('固定离线演示', markdown)

    def test_reports_keep_open_critical_issues_and_stopping_reason(self):
        report = demo_report()
        report['issues'][0]['status'] = 'open'
        report['issues'][0]['severity'] = 'critical'
        report['decision'], report['stop_reason'], report['status'] = 'blocked', 'round_limit', 'partial'
        for output in (render_html(report), render_markdown(report)):
            self.assertIn('I-001', output)
            self.assertIn('critical', output)
            self.assertIn('open', output)
            self.assertIn('达到轮数上限', output)
            self.assertIn('仍有阻断问题', output)

    def test_unreviewed_revision_cannot_replace_the_last_reviewed_headline(self):
        report = demo_report()
        report['proposal']['reviewed'] = False
        report['proposal']['version'] = 3
        report['proposal']['recommendation'] = 'UNREVIEWED_NEW_RECOMMENDATION'
        report['decision'], report['status'], report['stop_reason'] = 'undetermined', 'partial', 'provider_error'
        for output in (render_html(report), render_markdown(report)):
            self.assertIn('尚未复核', output)
            self.assertIn('最后完成审查', output)
            self.assertNotIn('UNREVIEWED_NEW_RECOMMENDATION', output)


class CliTests(unittest.TestCase):
    def invoke(self, args):
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(args)
        return code, stdout.getvalue(), stderr.getvalue()

    def test_demo_runs_without_credentials_and_writes_all_formats(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {}, clear=True):
            code, stdout, stderr = self.invoke(['--demo', '--out', directory, '--json', '--quiet'])
            self.assertEqual(code, 0, stderr)
            report = json.loads(stdout)
            self.assertTrue(report['demo'])
            self.assertEqual(report['actual_model_calls'], 0)
            self.assertEqual(report['verification_status'], 'not_checked')
            self.assertEqual(report['rounds_completed'], 2)
            for name in ['report.json', 'report.md', 'report.html']:
                self.assertTrue((Path(directory) / name).is_file())
            if os.name == 'posix':
                self.assertEqual((Path(directory) / 'report.json').stat().st_mode & 0o777, 0o600)

    def test_demo_cannot_pretend_to_analyze_a_custom_question(self):
        code, stdout, stderr = self.invoke(['--demo', 'analyze my real problem'])
        self.assertEqual(code, 1)
        self.assertIn('fixed example', stderr)

    def test_existing_report_is_preserved_unless_explicitly_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'report.json'
            marker.write_text('KEEP_ME', encoding='utf-8')
            code, _, error = self.invoke(['--demo', '--out', directory, '--quiet'])
            self.assertEqual(code, 1)
            self.assertIn('already exists', error)
            self.assertEqual(marker.read_text(), 'KEEP_ME')
            code, _, error = self.invoke(['--demo', '--out', directory, '--overwrite', '--quiet'])
            self.assertEqual(code, 0, error)
            self.assertTrue(json.loads(marker.read_text())['demo'])

    def test_live_run_without_settings_fails_before_any_network_call(self):
        with patch.dict(os.environ, {}, clear=True), patch('debate_direction.provider._http_transport') as network:
            code, _, error = self.invoke(['What should change?'])
            self.assertEqual(code, 1)
            self.assertIn('--model', error)
            network.assert_not_called()


if __name__ == '__main__':
    unittest.main()
