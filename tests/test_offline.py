import json, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import check_prices as cp

class MatchTests(unittest.TestCase):
    def test_cpu_exact_accepts(self):
        ok,_=cp.match_result({'id':'cpu'},{'title':'AMD Ryzen 9 9950X 16-Core Processor'})
        self.assertTrue(ok)
    def test_cpu_x3d_rejected(self):
        ok,_=cp.match_result({'id':'cpu'},{'title':'AMD Ryzen 9 9950X3D Processor'})
        self.assertFalse(ok)
    def test_used_result_rejected(self):
        ok,_=cp.match_result({'id':'cpu'},{'title':'Used AMD Ryzen 9 9950X'})
        self.assertFalse(ok)
    def test_approved_2tb_nvme_accepts(self):
        ok,_=cp.match_result({'id':'nvme-2tb'},{'title':'WD_BLACK SN850X 2TB NVMe SSD'})
        self.assertTrue(ok)
    def test_wrong_nvme_capacity_rejected(self):
        ok,_=cp.match_result({'id':'nvme-2tb'},{'title':'WD_BLACK SN850X 4TB NVMe SSD'})
        self.assertFalse(ok)

class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.old_data=cp.DATA; self.old_quota=cp.QUOTA_PATH; self.old_config=cp.CONFIG
        cp.DATA=Path(self.tmp.name); cp.QUOTA_PATH=cp.DATA/'quota_status.json'
        cp.CONFIG={'preflight':{'max_serpapi_searches_per_run':24,'serpapi_monthly_limit':250,'serpapi_reserve':10,'serpapi_monthly_budget':240}}
    def tearDown(self):
        cp.DATA=self.old_data; cp.QUOTA_PATH=self.old_quota; cp.CONFIG=self.old_config; self.tmp.cleanup()
    def test_quota_increment(self):
        cp.write_quota(cp.quota_state('2026-08-28T12:00:00+00:00'),'2026-08-28T12:00:00+00:00')
        q=cp.bump_quota('2026-08-28T12:01:00+00:00')
        self.assertEqual(q['checks_used'],1)
        self.assertEqual(q['checks_remaining_to_plan'],239)
        self.assertEqual(q['checks_remaining_absolute'],249)
    def test_month_rollover_resets(self):
        cp.QUOTA_PATH.write_text(json.dumps({'month':'2026-08','checks_used':239}))
        q=cp.quota_state('2026-09-01T00:00:00+00:00')
        self.assertEqual(q['checks_used'],0)
        self.assertEqual(q['checks_remaining_to_plan'],240)
    def test_selection_respects_remaining_budget(self):
        with patch.object(cp,'searchable_products',return_value=[{'id':str(i)} for i in range(20)]):
            self.assertEqual(len(cp.selected(24,3)),3)
            self.assertEqual(cp.selected(24,0),[])

class NoNetworkTests(unittest.TestCase):
    def test_missing_key_does_not_call_serp(self):
        old_data,old_obs,old_quota,old_products,old_config=cp.DATA,cp.OBS,cp.QUOTA_PATH,cp.PRODUCTS,cp.CONFIG
        try:
            with tempfile.TemporaryDirectory() as td:
                root=Path(td); (root/'observations').mkdir()
                cp.DATA=root; cp.OBS=root/'observations'; cp.QUOTA_PATH=root/'quota_status.json'
                cp.PRODUCTS=[{'id':'cpu','label':'CPU','model':'AMD Ryzen 9 9950X','price_source':'search','search_terms':['AMD Ryzen 9 9950X'],'retailer_search_urls':{'amazon':'x'}}]
                cp.CONFIG={'preflight':{'max_serpapi_searches_per_run':24,'serpapi_monthly_limit':250,'serpapi_reserve':10,'serpapi_monthly_budget':240}}
                (root/'config.json').write_text(json.dumps(cp.CONFIG)); (root/'collector_status.json').write_text('{}')
                with patch.dict(os.environ,{},clear=True), patch.object(cp,'serp',side_effect=AssertionError('network must not be called')):
                    cp.main()
                status=json.loads((root/'collector_status.json').read_text())
                self.assertEqual(status['searches_attempted'],0)
        finally:
            cp.DATA,cp.OBS,cp.QUOTA_PATH,cp.PRODUCTS,cp.CONFIG=old_data,old_obs,old_quota,old_products,old_config

class UiPolicyTests(unittest.TestCase):
    def test_ui_requires_strong_serpapi_match(self):
        html=(ROOT/'index.html').read_text()
        self.assertIn("o.method!=='serpapi_google_shopping'||o.match_status==='strong'",html)
        self.assertIn("latest?.status==='manual_review'",html)
        self.assertIn("data/quota_status.json",html)
        self.assertIn("price-check-v2.yml",html)

if __name__=='__main__': unittest.main()
