import json, os, sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from scripts import check_prices as cp

class MatchTests(unittest.TestCase):
 def ok(self,pid,title,price): return cp.match_result({'id':pid},{'title':title,'extracted_price':price},price)[0]
 def test_cpu_exact_accepts(self): self.assertTrue(self.ok('cpu-9950x3d','AMD Ryzen 9 9950X3D Processor',619.99))
 def test_cpu_x3d2_rejected(self): self.assertFalse(self.ok('cpu-9950x3d','AMD Ryzen 9 9950X3D2 Processor',799.99))
 def test_royal_neo_32_exact_accepts(self): self.assertTrue(self.ok('ram-royal-neo-32','G.Skill Trident Z5 Royal Neo Silver 32GB (2x16GB) DDR5-6000 CL28 F5-6000J2836G16GX2-TR5NS',499.99))
 def test_royal_neo_64_exact_accepts(self): self.assertTrue(self.ok('ram-royal-neo-64','G.Skill Trident Z5 Royal Neo Silver 64GB (2x32GB) DDR5-6000 CL30 F5-6000J3036G32GX2-TR5NS',699.99))
 def test_alt_ram_requires_2x32(self): self.assertFalse(self.ok('ram-64gb-alt','64GB DDR5-6000 CL30 White single DIMM',299.99))
 def test_alt_ram_accepts_white_2x32(self): self.assertTrue(self.ok('ram-64gb-alt','64GB DDR5-6000 CL30 White 2x32GB AMD EXPO Kit',299.99))
 def test_hydroshift_accepts(self): self.assertTrue(self.ok('cooler-hydroshift-ii','Lian Li HydroShift II OLED Curved 360 P28 White',269.99))
 def test_tryx_accepts(self): self.assertTrue(self.ok('cooler-tryx-panorama-se','TRYX Panorama SE 360 ARGB White',249.99))
 def test_psu_accepts(self): self.assertTrue(self.ok('psu-lianli-rs1200','Lian Li RS1200G 1200W White ATX 3.1 Power Supply',139.99))
 def test_reverse_fan_identity_required(self): self.assertFalse(self.ok('fans-lianli-tl120-reverse','Lian Li UNI FAN TL 120 White Standard Blade',99.99))
 def test_reverse_fan_accepts(self): self.assertTrue(self.ok('fans-lianli-tl120-reverse','Lian Li UNI FAN TL 120 Reverse White 3 Pack',99.99))
 def test_nm790_exact_accepts(self): self.assertTrue(self.ok('nvme-nm790-4tb','Lexar NM790 4TB PCIe Gen4 NVMe SSD',399.99))
 def test_wrong_nm790_capacity_rejected(self): self.assertFalse(self.ok('nvme-nm790-4tb','Lexar NM790 2TB PCIe Gen4 NVMe SSD',199.99))
 def test_aircooled_3090_accepts(self): self.assertTrue(self.ok('gpu-3090','EVGA GeForce RTX 3090 FTW3 Ultra 24GB',699.99))
 def test_3090_ti_rejected(self): self.assertFalse(self.ok('gpu-3090','GeForce RTX 3090 Ti 24GB',699.99))
 def test_waterblock_3090_rejected(self): self.assertFalse(self.ok('gpu-3090','EVGA RTX 3090 Hydro Copper 24GB Water Cooled',699.99))
 def test_5090_accepts(self): self.assertTrue(self.ok('gpu-5090','NVIDIA GeForce RTX 5090 32GB Graphics Card',2999.99))
 def test_a6000_accepts_used(self): self.assertTrue(self.ok('gpu-a6000-48gb','Used NVIDIA RTX A6000 48GB Graphics Card',2999.99))
 def test_pro5000_blackwell_accepts(self): self.assertTrue(self.ok('gpu-pro5000-blackwell-48gb','NVIDIA RTX PRO 5000 Blackwell 48GB Graphics Card',4999.99))
 def test_prebuilt_rejected(self): self.assertFalse(self.ok('gpu-5090','Gaming PC Desktop with RTX 5090 32GB',3999.99))
 def test_outlier_price_rejected(self): self.assertFalse(self.ok('gpu-3090','EVGA RTX 3090 24GB',299.99))
 def test_ambiguous_missing_title_stays_review(self): self.assertEqual(cp.classification('missing title'),'manual_review')

class QuotaTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.old_data=cp.DATA; self.old_quota=cp.QUOTA_PATH; self.old_config=cp.CONFIG; cp.DATA=Path(self.tmp.name); cp.QUOTA_PATH=cp.DATA/'quota_status.json'; cp.CONFIG={'preflight':{'max_serpapi_searches_per_run':24,'serpapi_monthly_limit':250,'serpapi_reserve':10,'serpapi_monthly_budget':240}}
 def tearDown(self): cp.DATA=self.old_data; cp.QUOTA_PATH=self.old_quota; cp.CONFIG=self.old_config; self.tmp.cleanup()
 def test_quota_increment(self): cp.write_quota(cp.quota_state('2026-09-03T12:00:00+00:00'),'2026-09-03T12:00:00+00:00'); self.assertEqual(cp.bump_quota('2026-09-03T12:01:00+00:00')['checks_used'],1)
 def test_month_rollover_resets(self): cp.QUOTA_PATH.write_text(json.dumps({'month':'2026-08','checks_used':239})); self.assertEqual(cp.quota_state('2026-09-01T00:00:00+00:00')['checks_used'],0)
 def test_selection_respects_remaining_budget(self):
  with patch.object(cp,'searchable_products',return_value=[{'id':str(i)} for i in range(20)]): self.assertEqual(len(cp.selected(24,3)),3); self.assertEqual(cp.selected(24,0),[])
 def test_retailer_fallback_query(self): self.assertEqual(cp.retailer_query({'id':'cpu-9950x3d','search_terms':['AMD Ryzen 9 9950X3D']},'bestbuy','2026-09-03T00:00:00+00:00'),'AMD Ryzen 9 9950X3D Best Buy')

class RevalidationTests(unittest.TestCase):
 def test_revalidation_rejects_bad_historical_row_without_network(self):
  old_obs,old_products=cp.OBS,cp.PRODUCTS
  try:
   with tempfile.TemporaryDirectory() as td:
    cp.OBS=Path(td); cp.PRODUCTS=[{'id':'gpu-3090','label':'3090'}]; (cp.OBS/'gpu-3090.json').write_text(json.dumps([{'method':'serpapi_google_shopping','status':'verified','match_status':'strong','model':'RTX 3090 Ti 24GB','price':699.99}]))
    with patch.object(cp,'serp',side_effect=AssertionError('network must not be called')): result=cp.revalidate_existing()
    row=json.loads((cp.OBS/'gpu-3090.json').read_text())[0]; self.assertEqual(row['status'],'rejected'); self.assertEqual(row['match_status'],'rejected'); self.assertEqual(result['trusted_rows'],0)
  finally: cp.OBS,cp.PRODUCTS=old_obs,old_products

class NoNetworkTests(unittest.TestCase):
 def test_missing_key_does_not_call_serp(self):
  old_data,old_obs,old_quota,old_products,old_config=cp.DATA,cp.OBS,cp.QUOTA_PATH,cp.PRODUCTS,cp.CONFIG
  try:
   with tempfile.TemporaryDirectory() as td:
    root=Path(td); (root/'observations').mkdir(); cp.DATA=root; cp.OBS=root/'observations'; cp.QUOTA_PATH=root/'quota_status.json'; cp.PRODUCTS=[{'id':'cpu-9950x3d','label':'CPU','model':'AMD Ryzen 9 9950X3D','price_source':'search','search_terms':['AMD Ryzen 9 9950X3D'],'retailer_search_urls':{'amazon':'x'}}]; cp.CONFIG={'preflight':{'max_serpapi_searches_per_run':24,'serpapi_monthly_limit':250,'serpapi_reserve':10,'serpapi_monthly_budget':240}}
    with patch.dict(os.environ,{},clear=True), patch.object(cp,'serp',side_effect=AssertionError('network must not be called')): cp.main()
    self.assertEqual(json.loads((root/'collector_status.json').read_text())['searches_attempted'],0)
  finally: cp.DATA,cp.OBS,cp.QUOTA_PATH,cp.PRODUCTS,cp.CONFIG=old_data,old_obs,old_quota,old_products,old_config

class UiPolicyTests(unittest.TestCase):
 def test_ui_requires_strong_serpapi_match(self):
  html=(ROOT/'index.html').read_text(); self.assertIn("o.method!=='serpapi_google_shopping'||o.match_status==='strong'",html); self.assertIn('data/quota_status.json',html); self.assertIn('price-check-v2.yml',html)

if __name__=='__main__': unittest.main()
