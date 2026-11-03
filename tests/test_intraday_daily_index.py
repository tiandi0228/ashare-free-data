"""Offline tests for the date-index of immutable research-only records."""
import base64,hashlib,json,unittest
from unittest.mock import patch
from collector.intraday_daily_index import build,persist
from tests.test_intraday_snapshot_archive import sample

REPO="test/repo"
DAY="2026-11-03"
FOLDER="snapshots/"+DAY

def archived(run_id,*,lost=False):
    snap=sample()
    if not lost:
        row=snap["symbols"]["002249"]
        row["quote"]={"quote_time":"2026-11-03T13:37:36+08:00",
                      "price":7.54,"volume_ratio":1.49}
        row["minute"]={"rows_today":166}
        row["validation"]["validation_issues"]=["MINUTE_COMPLETENESS_UNVERIFIED"]
    else:
        snap["symbols"]["002249"]={
            "status":"SOURCE_UNAVAILABLE","error_stage":"TENCENT_QUOTE",
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
            "executable_quote":False}
    raw=json.dumps(snap,sort_keys=True).encode()
    path=f"{FOLDER}/run_{run_id}_attempt_1.json"
    meta={"type":"file","name":f"run_{run_id}_attempt_1.json",
          "path":path,"sha":"blob_"+str(run_id)}
    saved={"path":path,"sha":meta["sha"],
           "content":base64.b64encode(raw).decode()}
    return meta,saved

class DailyIndexTests(unittest.TestCase):
    def test_rebuild_from_remote_readback(self):
        first,first_saved=archived(100)
        second,second_saved=archived(101,lost=True)
        with patch("collector.intraday_daily_index.api",
                   side_effect=[[second,first],second_saved,first_saved]):
            result=build(REPO,DAY)
        self.assertEqual(result["entries_count"],2)
        self.assertEqual([x["run_id"] for x in result["entries"]],[100,101])
        self.assertEqual(result["latest_by_symbol"]["002249"]["status"],
                         "SOURCE_UNAVAILABLE")
        self.assertIsNone(result["latest_by_symbol"]["002249"]["observed_price_cny"])
        self.assertTrue(result["index_is_not_live_quote"])
        self.assertFalse(result["minute_data_complete_certified"])
        self.assertFalse(result["cross_source_price_certified"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])

    def test_wrong_archive_sha_rejected(self):
        meta,saved=archived(100)
        meta["sha"]="replaced"
        with patch("collector.intraday_daily_index.api",
                   side_effect=[[meta],saved]):
            with self.assertRaisesRegex(ValueError,"identity changed"):
                build(REPO,DAY)

    def test_injected_archive_filename_rejected(self):
        meta,saved=archived(100)
        meta["name"]="../../danger.json"
        with patch("collector.intraday_daily_index.api",return_value=[meta]):
            with self.assertRaisesRegex(ValueError,"unrecognized"):
                build(REPO,DAY)

    def test_archive_day_mismatch_rejected(self):
        meta,saved=archived(100)
        with patch("collector.intraday_daily_index.api",
                   side_effect=[[meta],saved]):
            with self.assertRaisesRegex(ValueError,"unrecognized"):
                build(REPO,"2026-11-04")

    def test_index_create_readback(self):
        index={"date":DAY,"entries_count":1,"trade_gate":"BLOCKED"}
        raw=(json.dumps(index,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
        result={"path":f"indexes/{DAY}.json",
                "content":base64.b64encode(raw).decode()}
        with patch("collector.intraday_daily_index.api",
                   side_effect=[None,{},result]) as api:
            receipt=persist(REPO,index)
        payload=api.call_args_list[1].kwargs["data"]
        self.assertNotIn("sha",payload)
        self.assertEqual(payload["branch"],"research-intraday-snapshots")
        self.assertEqual(receipt["status"],"INDEX_VERIFIED")
        self.assertEqual(receipt["trade_gate"],"BLOCKED")

    def test_index_update_is_conditional_on_current_sha(self):
        index={"date":DAY,"entries_count":2,"trade_gate":"BLOCKED"}
        current={"path":f"indexes/{DAY}.json","sha":"prior",
                 "content":base64.b64encode(b"{}").decode()}
        raw=(json.dumps(index,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
        updated={"path":current["path"],"sha":"new",
                 "content":base64.b64encode(raw).decode()}
        with patch("collector.intraday_daily_index.api",
                   side_effect=[current,{},updated]) as api:
            persist(REPO,index)
        self.assertEqual(api.call_args_list[1].kwargs["data"]["sha"],"prior")

    def test_index_idempotent_when_same_bytes(self):
        index={"date":DAY,"entries_count":1,"trade_gate":"BLOCKED"}
        raw=(json.dumps(index,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode()
        old={"path":f"indexes/{DAY}.json","sha":"old",
             "content":base64.b64encode(raw).decode()}
        with patch("collector.intraday_daily_index.api",return_value=old) as api:
            receipt=persist(REPO,index)
        self.assertEqual(api.call_count,1)
        self.assertEqual(receipt["status"],"UNCHANGED")

    def test_index_corrupt_readback_rejected(self):
        index={"date":DAY,"entries_count":1}
        bad={"path":f"indexes/{DAY}.json","content":base64.b64encode(b"{}").decode()}
        with patch("collector.intraday_daily_index.api",
                   side_effect=[None,{},bad]):
            with self.assertRaisesRegex(ValueError,"mismatch"):
                persist(REPO,index)

if __name__=="__main__":unittest.main()
