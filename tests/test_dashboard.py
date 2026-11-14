"""Behavioral checks for privacy, calendar math and failure preservation."""
import datetime as dt
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location('dashboard', Path(__file__).parents[1]/'scripts/dashboard.py')
dashboard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class DashboardTests(unittest.TestCase):
    def test_streak_today_grace_and_window_boundary(self):
        days = [{'count': n} for n in [1, 1, 0, 2, 3, 0]]
        self.assertEqual(dashboard.streaks(days), (2, 2))
        self.assertEqual(dashboard.streaks([{'count': 1}]*365), (365, 365))
        self.assertEqual(dashboard.streaks([{'count': 0}]*365), (0, 0))
        self.assertEqual(dashboard.streaks([{'count': 1}, {'count': 0}, {'count': 0}]), (0, 1))

    def test_calendar_parser_handles_zero_singular_and_comma_counts(self):
        parser = dashboard.CalendarParser()
        for i, label in enumerate(['No contributions', '1 contribution', '1,234 contributions']):
            parser.feed(f'<td id="d{i}" data-date="2026-11-{i+1:02d}"></td><tool-tip for="d{i}">{label} on November {i+1}.</tool-tip>')
        self.assertEqual(parser.counts, {'d0': 0, 'd1': 1, 'd2': 1234})

    def test_calendar_incomplete_does_not_silently_invent_zeros(self):
        with patch.object(dashboard, 'request', return_value='<html></html>'):
            with self.assertRaisesRegex(ValueError, 'incomplete'):
                dashboard.calendar('example', dt.date(2026,11,13))

    def test_calendar_requests_public_endpoint_without_token(self):
        today=dt.date(2026,11,13)
        first=today-dt.timedelta(days=364)
        html=''.join(f'<td id="d{i}" data-date="{first+dt.timedelta(days=i)}"></td><tool-tip for="d{i}">1 contribution on date.</tool-tip>' for i in range(365))
        with patch.object(dashboard, 'request', return_value=html) as request:
            days=dashboard.calendar('example', today)
        self.assertEqual(len(days),365)
        self.assertEqual(days[-1],{'date': '2026-11-13','count':1})
        self.assertEqual(request.call_args.kwargs, {'raw': True})

    def test_private_repository_rejected_before_network_access(self):
        with patch.object(dashboard, 'request') as request:
            with self.assertRaisesRegex(ValueError, 'non-public'):
                dashboard.inspect_repo({'private':True},'sensitive-test-credential')
            request.assert_not_called()

    def test_manifest_detection_does_not_treat_substrings_as_packages(self):
        matches=dashboard.detect_dependencies('requirements.txt','fastapi==0.115\nflasker==1\npsycopg2-binary>=2')
        self.assertIn(('Frameworks','FastAPI'),matches)
        self.assertIn(('Databases','PostgreSQL'),matches)
        self.assertNotIn(('Frameworks','Flask'),matches)
        package=json.dumps({'description':'react next', 'dependencies':{'express':'*','@aws-sdk/client-s3':'*'}})
        self.assertEqual(dashboard.detect_dependencies('package.json',package),{('Frameworks','Express'),('Infrastructure','AWS SDK')})

    def test_repo_pagination(self):
        with patch.object(dashboard,'request',side_effect=[[{}]*100,[{}]*3]) as request:
            self.assertEqual(len(dashboard.pages('/users/test/repos?type=owner',None)),103)
            self.assertIn('page=2',request.call_args.args[0])

    def test_failed_fetch_preserves_live_files(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            (root/'README.md').write_text('last good dashboard')
            (root/'dashboard.config.json').write_text(json.dumps({'username':'example','include_forks':False,'include_archived':False,'featured':[]}))
            with patch.object(dashboard,'ROOT',root), patch.object(dashboard,'collect',side_effect=RuntimeError('network unavailable')), patch('sys.argv',['dashboard.py']):
                with self.assertRaisesRegex(RuntimeError,'network unavailable'):
                    dashboard.main()
            self.assertEqual((root/'README.md').read_text(),'last good dashboard')
            self.assertFalse((root/'assets').exists())

    def test_collect_masks_totals_and_accepts_compact_public_pr_events(self):
        repo={'name':'project','full_name':'example/project','html_url':'https://github.com/example/project',
              'owner':{'login':'example'},'private':False,'fork':False,'archived':False,
              'language':'Python','stargazers_count':2,'description':'A public project',
              'pushed_at':'2026-11-01T00:00:00Z','updated_at':'2026-11-01T00:00:00Z','homepage':None}
        user={'name':'Example','created_at':'2020-01-01T00:00:00Z','total_private_repos':9876}
        events=[{'public':True,'type':'PullRequestEvent','created_at':'2026-11-13T00:00:00Z',
                 'repo':{'name':'public-org/project'},'payload':{'action':'opened','pull_request':{'number':7}}},
                {'public':False,'type':'PullRequestEvent','repo':{'name':'private-org/secret'}}]
        config={'username':'example','include_forks':False,'include_archived':False,
                'featured':[{'repo':'project'}]}
        scan={'name':'project','url':repo['html_url'],'languages':{'Python':20},'technologies':[]}
        with patch.object(dashboard,'request',side_effect=[user,events]), patch.object(dashboard,'pages',return_value=[repo]), patch.object(dashboard,'inspect_repo',return_value=scan), patch.object(dashboard,'calendar',return_value=[{'date':'2026-11-13','count':1}]*365):
            data=dashboard.collect(config,'test-token-not-real')
        self.assertEqual((data['total_repos'],data['private_repos'],data['public_repos']),('?','?',1))
        self.assertEqual(data['recent'][0]['url'],'https://github.com/public-org/project/pull/7')
        output=json.dumps(data)
        for sensitive in ['9876','total_private_repos','private-org','test-token-not-real']:
            self.assertNotIn(sensitive,output)

    def test_svg_escapes_untrusted_text(self):
        svg=dashboard.SVG(420,'<unsafe & title>')
        svg.text(24,24,'<script>alert("x")</script> & data')
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'test.svg'
            svg.save(path,100)
            parsed=ET.parse(path)
            self.assertFalse(parsed.findall('.//{http://www.w3.org/2000/svg}script'))
            self.assertIn('&lt;script&gt;',path.read_text())


if __name__=='__main__':
    unittest.main()
