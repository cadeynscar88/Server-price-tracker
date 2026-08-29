import json, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from scripts import check_prices as cp

class MatchTests(unittest.TestCase):
    def ok(self,pid,title,price): return cp.match_result({'id':pid},{'title':title,'extracted_price':price},price)[0]
    def test_cpu_exact_accepts(self): self.assertTrue(self.ok('cpu','AMD Ryzen 9 9950X 16-Core Processor',599.99))
    def test_cpu_x3d_rejected(self): self.assertFalse(self.ok('cpu','AMD Ryzen 9 9950X3D Processor',699.99))
    def test_cpu_bulk_rejected(self): self.assertFalse(self.ok('cpu','AMD Ryzen 9 9950X Bulk Processor',450.99))
    def test_used_result_rejected(self): self.assertFalse(self.ok('cpu','Used AMD Ryzen 9 9950X',499.99))
    def test_gpu_monitor_bundle_rejected(self): self.assertFalse(self.ok('gpu-5070ti','RTX 5070 Ti 16GB Graphics Card Bundle with 34 inch Monitor',1499.99))
    def test_gpu_prebuilt_rejected(self): self.assertFalse(self.ok('gpu-pro4500','Workstation PC with NVIDIA RTX PRO 4500 Blackwell 32GB',2499.99))
    def test_gpu_outlier_price_rejected(self): self.assertFalse(self.ok('gpu-pro4500','NVIDIA RTX PRO 4500 Blackwell 32GB Graphics Card',8099.99))
    def test_ram_outlier_price_rejected(self): self.assertFalse(self.ok('ram-64gb','64GB DDR5 2x32GB Memory Kit',1255.99))
    def test_ram_requires_two_dimm_kit(self): self.assertFalse(self.ok('ram-96gb','96GB DDR5 48GB Memory',399.99))
    def test_case_walnut_rejected(self): self.assertFalse(self.ok('case','Lian Li LANCOOL 217 Walnut ATX Case',119.99))
    def test_case_inf_rejected(self): self.assertFalse(self.ok('case','Lian Li LANCOOL 217 INF Black ATX Case',124.99))
    def test_case_black_accepts(self): self.assertTrue(self.ok('case','Lian Li LANCOOL 217 Black ATX Case',119.99))
    def test_approved_2tb_nvme_accepts(self): self.assertTrue(self.ok('nvme-2tb','WD_BLACK SN850X 2TB NVMe SSD',149.99))
    def test_wrong_nvme_capacity_rejected(self): self.assertFalse(self.ok('nvme-2tb','WD_BLACK SN850X 4TB NVMe SSD',299.99))
    def test_boot_outlier_rejected(self): self.assertFalse(self.ok('boot-ssd','Samsung 870 EVO 500GB SATA SSD',299.75))

class QuotaTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.old_data=cp.DATA; self.old_quota=cp.QUOTA_PATH; self.old_config=cp.CONFIG
        cp.DATA=Path(self.tmp.name); cp.QUOTA_PATH=cp.DATA/'quota_status.json'; cp.CONFIG={'preflight':{'max_serpapi_searches_per_run':24,'serpapi_monthly_limit':250,'serpapi_reserve':10,'serpapi_monthly_budget':240}}
    def tearDown(self): cp.DATA=self.old_data; cp.QUOTA_PATH=self.old_quota; cp.CONFIG=self.old_config; self.tmp.cleanup()
    def test_quota_increment(self):
        cp.write_quota(cp.quota_state('2026-08-28T12:00:00+00:00'),'2026-08-28T12:00:00+00:00'); q=cp.bump_quota('2026-08-28T12:01:00+00:00')
        self.assertEqual(q['checks_used'],1); self.assertEqual(q['checks_remaining_to_plan'],239); self.assertEqual(q['checks_remaining_absolute'],249)
    def test_month_rollover_resets(self):
        cp.QUOTA_PATH.write_text(json.dumps({'month':'2026-08','checks_used':239})); q=cp.quota_state('2026-09-01T00:00:00+00:00')
        self.assertEqual(q['checks_used'],0); self.assertEqual(q['checks_remaining_to_plan'],240)
    def test_selection_respects_remaining_budget(self):
        with patch.object(cp,'searchable_products',return_value=[{'id':str(i)} for i in range(20)]): self.assertEqual(len(cp.selected(24,3)),3); self.assertEqual(cp.selected(24,0),[])
    def test_storage_query_rotates_exact_approved_family_without_extra_search(self):
        p={'id':'nvme-4tb','search_terms':['4TB NVMe SSD']}; q=cp.search_query(p,'2026-08-28T00:00:00+00:00')
        self.assertIn(q,cp.STORAGE_QUERIES['nvme-4tb']); self.assertNotEqual(q,'4TB NVMe SSD')

class RevalidationTests(unittest.TestCase):
    def test_revalidation_downgrades_bad_historical_row_without_network(self):
        old_obs,old_products=cp.OBS,cp.PRODUCTS
        try:
            with tempfile.TemporaryDirectory() as td:
                cp.OBS=Path(td); cp.PRODUCTS=[{'id':'gpu-pro4500','label':'GPU'}]
                (cp.OBS/'gpu-pro4500.json').write_text(json.dumps([{'method':'serpapi_google_shopping','status':'verified','match_status':'strong','model':'Workstation PC with NVIDIA RTX PRO 4500 Blackwell 32GB','price':8099.99}]))
                with patch.object(cp,'serp',side_effect=AssertionError('network must not be called')): result=cp.revalidate_existing()
                row=json.loads((cp.OBS/'gpu-pro4500.json').read_text())[0]
                self.assertEqual(row['status'],'manual_review'); self.assertEqual(row['match_status'],'review'); self.assertEqual(result['changed'],1)
        finally: cp.OBS,cp.PRODUCTS=old_obs,old_products

class NoNetworkTests(unittest.TestCase):
    def test_missing_key_does_not_call_serp(self):
        old_data,old_obs,old_quota,old_products,old_config=cp.DATA,cp.OBS,cp.QUOTA_PATH,cp.PRODUCTS,cp.CONFIG
        try:
            with tempfile.TemporaryDirectory() as td:
                root=Path(td); (root/'observations').mkdir(); cp.DATA=root; cp.OBS=root/'observations'; cp.QUOTA_PATH=root/'quota_status.json'
                cp.PRODUCTS=[{'id':'cpu','label':'CPU','model':'AMD Ryzen 9 9950X','price_source':'search','search_terms':['AMD Ryzen 9 9950X'],'retailer_search_urls':{'amazon':'x'}}]
                cp.CONFIG={'preflight':{'max_serpapi_searches_per_run':24,'serpapi_monthly_limit':250,'serpapi_reserve':10,'serpapi_monthly_budget':240}}
                (root/'config.json').write_text(json.dumps(cp.CONFIG)); (root/'collector_status.json').write_text('{}')
                with patch.dict(os.environ,{},clear=True), patch.object(cp,'serp',side_effect=AssertionError('network must not be called')): cp.main()
                status=json.loads((root/'collector_status.json').read_text()); self.assertEqual(status['searches_attempted'],0)
        finally: cp.DATA,cp.OBS,cp.QUOTA_PATH,cp.PRODUCTS,cp.CONFIG=old_data,old_obs,old_quota,old_products,old_config

class UiPolicyTests(unittest.TestCase):
    def test_ui_requires_strong_serpapi_match(self):
        html=(ROOT/'index.html').read_text(); self.assertIn("o.method!=='serpapi_google_shopping'||o.match_status==='strong'",html); self.assertIn("latest?.status==='manual_review'",html); self.assertIn("data/quota_status.json",html); self.assertIn("price-check-v2.yml",html)

if __name__=='__main__': unittest.main()
