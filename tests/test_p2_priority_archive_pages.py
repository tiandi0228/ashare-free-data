"""Select actual archived work from durable coverage, never from untrusted claims."""
import unittest
from collector.p2_paged_real_archive import select_page

def indexed(n):
    return [(i,None) for i in range(n)]
def coverage(unseen,gaps=()):
    return {
        "phase":"P2_PERSISTENT_ARCHIVE_FEATURE_COVERAGE",
        "status":"DURABLE_RESEARCH_PAGE_COVERAGE_NOT_CERTIFIED",
        "source_epoch_sha256":"a"*64,
        "trade_gate":"BLOCKED","historical_PIT_verified":False,
        "coverage_certified_for_trading":False,"orders":[],
        "unobserved_shard_ids":[f"shard_{i:04d}" for i in unseen],
        "gap_shard_ids":[f"shard_{i:04d}" for i in gaps]}
class PriorityTests(unittest.TestCase):
    def test_first_page_with_most_missing_wins(self):
        v=select_page(indexed(35),"a"*64,run_number=3,coverage=coverage(range(16,32)))
        self.assertEqual(v,(1,"PRIORITIZE_UNOBSERVED_SHARDS"))
    def test_short_last_page_not_preferred_over_full_page(self):
        v=select_page(indexed(35),"a"*64,run_number=3,
                      coverage=coverage(list(range(16,32))+[34]))
        self.assertEqual(v[0],1)
    def test_gap_priority_after_every_page_observed(self):
        self.assertEqual(select_page(indexed(34),"a"*64,1,
                         coverage=coverage([],list(range(16,32)))),
                         (1,"RECHECK_FEATURE_GAP_SHARDS"))
    def test_completed_pages_rotate(self):
        self.assertEqual(select_page(indexed(34),"a"*64,3,
                         coverage=coverage([]))[0],2)
    def test_wrong_epoch_is_not_used(self):
        self.assertEqual(select_page(indexed(34),"b"*64,2,
                         coverage=coverage(range(16,32)))[0],1)
    def test_malicious_coverage_hint_is_rejected(self):
        for mutation in (
            lambda x:x.update(unobserved_shard_ids=["shard_9999"]),
            lambda x:x.update(unobserved_shard_ids=["shard_0017","shard_0017"]),
            lambda x:x.update(trade_gate="OPEN"),
            lambda x:x.update(orders=[{"side":"BUY"}]),
            lambda x:x.update(unobserved_shard_ids=["shard_0017"],gap_shard_ids=["shard_0017"]),
        ):
            with self.subTest(mutation=mutation):
                c=coverage(range(16,32))
                mutation(c)
                result=select_page(indexed(34),"a"*64,1,coverage=c)
                self.assertEqual(result[0],0)
    def test_explicit_page_overrides_summary_and_bounds(self):
        self.assertEqual(select_page(indexed(34),"a"*64,1,page=2,
                         coverage=coverage(range(16,32))), (2,"EXPLICIT_PAGE"))
        with self.assertRaises(ValueError):
            select_page(indexed(34),"a"*64,1,page=3,coverage=coverage([]))
if __name__=="__main__":unittest.main()
