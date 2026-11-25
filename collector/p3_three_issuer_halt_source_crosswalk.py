"""Research-only crosswalk of three issuer-authored halt/resume PDF references.

This validates the exact immutable P2 gap identities and the curated dated
issuer-authored document references. It does NOT independently download or
hash the PDFs, prove exchange publisher origin or certify every PIT session.
"""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

EPOCH="5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"
SHAS={
"sh.600293":("shard_0027","f18062e301843b403e52aa4ca7dbac511579a6f9683da74b414451a8ab38d56c",10),
"sh.600301":("shard_0027","2f163fecfb61ea758ecdbd98edb1d7a4b05c32172a78df31801ec3b9f3d5a5f4",5),
"sh.603400":("shard_0161","d7d67226a1430bc3c0a56a4e48f08871f1a6dfb996043cc8f6d5c1523a6d60f5",10),
}
DOCUMENTS={
"sh.600293":(("2026-031","2026-09-29","halt","1225586063"),("2026-036","2026-10-20","resume","1225611307")),
"sh.600301":(("2026-054","2026-09-19","resume","1225571318"),),
"sh.603400":(("2026-051","2026-09-30","resume","1225588894"),),
}
WINDOWS={
"sh.600293":("2026-09-29","2026-10-20"),
"sh.600301":("2026-09-14","2026-09-21"),
"sh.603400":("2026-09-15","2026-09-30")
}
def crosswalk(triage,manifest):
    if (not isinstance(triage,dict) or triage.get("source_epoch_sha256")!=EPOCH
        or triage.get("phase")!="P2_ORIGINAL_SHA_VERIFIED_FEATURE_GAP_RESEARCH_TRIAGE"
        or triage.get("trade_gate")!="BLOCKED"
        or triage.get("historical_PIT_verified") is not False
        or triage.get("orders")!=[] or triage.get("executable_candidates")!=[]
        or triage.get("unresolved_issuers")!=16
        or triage.get("feature_complete_shards")!=226
        or triage.get("observed_shards")!=241):
        raise ValueError("unsafe original P2 gap report")
    if (not isinstance(manifest,dict)
        or manifest.get("phase")!="P3_ISSUER_AUTHORED_HALT_RESUME_PDF_RESEARCH_REFERENCES"
        or manifest.get("trade_gate")!="BLOCKED"
        or manifest.get("orders")!=[] or manifest.get("executable_candidates")!=[]
        or any(manifest.get(k) is not False for k in (
           "publisher_origin_independently_authenticated",
           "pdf_original_bytes_sha_verified_in_this_audit",
           "first_publication_instant_authenticated","historical_PIT_verified"))):
        raise ValueError("unverified PDFs misrepresented as authenticated")
    items=triage.get("research_actions")
    if not isinstance(items,list) or len(items)!=16:
        raise ValueError("missing original gap queue")
    gap={x["issuer"]:x for x in items}
    pairs=manifest.get("pairs")
    if not isinstance(pairs,list) or len(pairs)!=3:
        raise ValueError("not exact three issuer pairs")
    found={}
    for row in pairs:
        if not isinstance(row,dict):raise ValueError("invalid row")
        code=row.get("issuer")
        if code not in SHAS or code in found:
            raise ValueError("unexpected or duplicate issuer")
        shard,sha,count=SHAS[code]
        g=gap.get(code)
        if (not isinstance(g,dict)
            or row.get("shard")!=shard
            or row.get("original_csv_sha256")!=sha
            or row.get("vendor_suspended_rows_last_21")!=count
            or g.get("shard_id")!=shard
            or g.get("original_csv_sha256")!=sha
            or g.get("suspended_rows_last_21")!=count
            or g.get("category")!="VENDOR_SUSPENDED_IN_LAST_21_ROWS"
            or g.get("gap_resolved") is not False
            or g.get("eligible_for_feature_complete_promotion") is not False
            or (row.get("halt_start"),row.get("resume_day"))!=WINDOWS[code]):
            raise ValueError("issuer original gap/announcement mismatch")
        docs=row.get("docs")
        if not isinstance(docs,list) or len(docs)!=len(DOCUMENTS[code]):
            raise ValueError("missing issuer source documents")
        for doc, expected in zip(docs,DOCUMENTS[code]):
            if not isinstance(doc,dict):raise ValueError("bad document")
            ann,day,kind,docid=expected
            if (doc.get("announcement")!=ann or doc.get("date")!=day
                or doc.get("kind")!=kind
                or doc.get("url") !=
                f"https://static.cninfo.com.cn/finalpage/{day}/{docid}.PDF"):
                raise ValueError("source URL or publication date changed")
        found[code]={
            "shard_id":shard,"vendor_suspended_rows_last_21":count,
            "halt_start_claim":row["halt_start"],
            "resume_day_claim":row["resume_day"],
            "issuer_authored_documents":len(docs),
            "source_document_references_reviewed":True,
            "original_pdf_bytes_sha_verified":False,
            "official_full_daily_halt_calendar_certified":False,
            "gap_resolved":False,
            "promote_shard_to_feature_complete":False,
        }
    if set(found)!=set(SHAS):
        raise ValueError("incomplete issuer documents")
    return {
        "phase":"P2_P3_THREE_ISSUER_HALT_RESUME_SOURCE_CROSSWALK",
        "source_epoch_sha256":EPOCH,"referenced_issuers":found,
        "reviewed_issuer_count":3,
        "remaining_vendor_suspension_issuer_count":12,
        "remaining_all_gap_issuer_count":16,
        "remaining_gap_shards":15,
        "research_feature_complete_shards":226,
        "research_observed_shards":241,
        "source_pdf_originals_byte_sha_verified":False,
        "official_complete_pit_halt_interval_certified":False,
        "historical_PIT_verified":False,
        "feature_shards_promoted":0,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[],
    }
def main():
    p=argparse.ArgumentParser()
    p.add_argument("--triage",type=Path,required=True)
    p.add_argument("--sources",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    r=crosswalk(json.loads(a.triage.read_text()),json.loads(a.sources.read_text()))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({k:r[k] for k in ("phase","reviewed_issuer_count",
        "remaining_vendor_suspension_issuer_count","research_feature_complete_shards",
        "feature_shards_promoted","trade_gate")},ensure_ascii=False))
if __name__=="__main__":main()
