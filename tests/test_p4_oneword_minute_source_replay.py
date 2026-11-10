import copy
import hashlib
import unittest

from collector.p4_oneword_minute_source_replay import replay
from collector.p4_oneword_prediction_replay import RULE


def frozen():
    return {"issuer": "sz.000069", "predicted_on": "2026-11-10",
            "session_on": "2026-11-11", "prediction": "ONE_WORD_LIMIT_UP",
            "prediction_rule": RULE, "trade_gate": "BLOCKED", "orders": []}


def sample(low="1.87", issuer="sz.000069", day="2026-11-11"):
    return ("session_on,time,issuer,open,high,low,close,volume\n"
            f"{day},09:30,{issuer},1.87,1.87,{low},1.87,100\n"
            f"{day},09:31,{issuer},1.87,1.87,1.87,1.87,200\n").encode()


def metadata(raw):
    return {"source_ref": "https://example.test/vendor-minute",
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "claimed_full_trading_session": False,
            "official_exchange_origin_authenticated": False,
            "claimed_limit_up_price": "1.87",
            "claimed_previous_close": "1.70"}


class MinuteOneWordReplayTests(unittest.TestCase):
    def test_matching_minute_rows_are_only_compatible(self):
        raw=sample()
        result=replay(frozen(),raw,metadata(raw))
        self.assertEqual(result["audit_state"],"MINUTE_BARS_COMPATIBLE_ONE_WORD_NOT_CERTIFIED")
        self.assertEqual(result["observed_minute_rows"],2)
        self.assertTrue(result["raw_csv_sha256_checked"])
        self.assertFalse(result["one_word_limit_up_certified"])
        self.assertFalse(result["opening_auction_independently_authenticated"])
        self.assertEqual(result["trade_gate"],"BLOCKED")
        self.assertEqual(result["orders"],[])

    def test_trade_below_limit_contradicts_claimed_one_word(self):
        raw=sample("1.85")
        result=replay(frozen(),raw,metadata(raw))
        self.assertEqual(result["audit_state"],"CONTRADICTED_BY_LOCALLY_REPLAYED_MINUTE_LOW")
        self.assertEqual(result["first_contradictory_minute"],"09:30")
        self.assertFalse(result["forecast_accuracy_claimed"])

    def test_mutating_source_bytes_breaks_digest(self):
        raw=sample()
        wrong=sample("1.86")
        with self.assertRaisesRegex(ValueError,"SHA mismatch"):
            replay(frozen(),wrong,metadata(raw))

    def test_issuer_date_and_time_scope_strict(self):
        raw=sample(issuer="sz.000058")
        with self.assertRaisesRegex(ValueError,"cross-date or cross-issuer"):
            replay(frozen(),raw,metadata(raw))
        raw=sample(day="2026-11-10")
        with self.assertRaisesRegex(ValueError,"cross-date or cross-issuer"):
            replay(frozen(),raw,metadata(raw))
        raw=sample().replace(b"09:31",b"09:30")
        with self.assertRaisesRegex(ValueError,"duplicate or nonchronological"):
            replay(frozen(),raw,metadata(raw))

    def test_cannot_claim_exchange_authentication_through_flag(self):
        raw=sample()
        info=metadata(raw)
        info["claimed_full_trading_session"]=True
        info["official_exchange_origin_authenticated"]=True
        result=replay(frozen(),raw,info)
        self.assertFalse(result["official_source_authenticated_by_this_replay"])
        self.assertFalse(result["original_tick_stream_independently_replayed"])
        self.assertFalse(result["official_security_price_limit_authenticated"])

    def test_bad_price_and_volume_and_ohlc_are_rejected(self):
        for raw in (
            sample().replace(b"1.87,1.87,1.87,1.87,200",b"1.87,1.85,1.87,1.87,200"),
            sample().replace(b",100\n",b",NaN\n"),
            sample().replace(b",100\n",b",-1\n"),
            sample().replace(b"1.87,1.87,1.87,1.87,200",b"1.88,1.88,1.88,1.88,200"),
        ):
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                replay(frozen(),raw,metadata(raw))

    def test_cannot_mix_forged_daily_price_and_raw_minutes(self):
        raw=sample()
        p=frozen()
        p["observation"]={"session_on":"2026-11-11"}
        with self.assertRaises(ValueError):
            replay(p,raw,metadata(raw))

    def test_reject_out_of_session_and_zero_volume(self):
        raw=sample().replace(b"09:30",b"12:00")
        with self.assertRaisesRegex(ValueError,"invalid intraday time|outside observed"):
            replay(frozen(),raw,metadata(raw))
        raw=sample().replace(b",100\n",b",0\n").replace(b",200\n",b",0\n")
        with self.assertRaisesRegex(ValueError,"no actual traded volume"):
            replay(frozen(),raw,metadata(raw))

    def test_reject_forged_trade_order(self):
        raw=sample()
        p=frozen()
        p["orders"]=[{"side":"BUY"}]
        with self.assertRaisesRegex(ValueError,"executable order"):
            replay(p,raw,metadata(raw))


if __name__ == "__main__":
    unittest.main()
