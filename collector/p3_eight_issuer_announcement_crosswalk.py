"""Bind eight sourced but NOT byte-authenticated issuer disclosures to live P2 gaps.

Research URL discovery is not an exchange PIT calendar or authorization to
promote a feature shard. Fail closed on changed original CSV identities,
retroactive ST exclusion or fabricated PDF hash.
"""
import argparse,json,re
from pathlib import Path
from urllib.parse import urlsplit

EPOCH="5ba00fbd720fad90c343591cc33e885b824adf182306b893e5b3ed4030bff022"
PHASE="P3_EIGHT_ISSUER_DISCLOSURE_RESEARCH_CROSSWALK_READ_ONLY"
PDF_PATH=re.compile(r"/finalpage/\d{4}-\d{2}-\d{2}/\d+\.PDF\Z")
SHA=re.compile(r"[0-9a-f]{64}\Z")
EXPECTED={
"sh.601238":("shard_0104","a2f6d4f36ec5487329a8e66a56bdf872c4dfc1e9a1cb2eb565994628800b7e65","2026-09-14","2026-09-29",None),
"sh.601995":("shard_0120","c62152568423890c5bfc384fa4e0ec34e9ef71b9a092011b75b83a9e282d6609","2026-09-15","2026-09-23",None),
"sh.603183":("shard_0140","3f53cf0bd447c2d757488614b4236632069885e793ee04959ae0c888c614168c","2026-09-30","2026-10-09",None),
"sh.603517":("shard_0166","f6e5848ea8ff0e682608d96342adf68594140f9e7eac3aaad75afbfb2dc2394a","2026-10-19","2026-10-20","2026-10-20"),
"sh.603759":("shard_0182","b5d17da3ca737e21479b5e4b5a1ad41c7f13f777f42b8eaf419f30c35dcce4dc","2026-10-19","2026-10-20",None),
"sh.603838":("shard_0186","98441e8dcbfae442ec14a7004a95ce5abff8d876b8cd69e1e754a77b16436e86","2026-10-19","2026-10-20","2026-10-20"),
"sz.002860":("shard_0378","c1e9e5844abed70f2471cb337bf917f584f0029109aac7c0bfb80ae85ad1d188","2026-09-22","2026-10-14",None),
"sz.002870":("shard_0379","9f69a30a532df4e4178109d0c886f30c82e1f8fd1cf9e0fb3693f13582d3935a","2026-09-01","2026-09-15",None)
}
def reconcile(queue,refs):
    if (not isinstance(queue,dict) or not isinstance(refs,dict)
        or queue.get("phase")!="P2_P3_LIVE_FEATURE_GAP_AND_ISSUER_DISCLOSURE_RESEARCH_QUEUE"
        or queue.get("source_epoch_sha256")!=EPOCH
        or queue.get("missing_p3_halt_source_reference_issuer_count")!=8
        or queue.get("curated_p3_reference_issuer_count")!=7
        or queue.get("unresolved_gap_issuers")!=16
        or queue.get("trade_gate")!="BLOCKED" or queue.get("historical_PIT_verified") is not False
        or queue.get("orders")!=[] or queue.get("executable_candidates")!=[]
        or refs.get("phase")!="P3_EIGHT_PREVIOUSLY_UNLINKED_ISSUER_DATED_DISCLOSURE_RESEARCH_V1"
        or refs.get("source_epoch_sha256")!=EPOCH
        or refs.get("asof_vendor_day")!="2026-10-20"
        or refs.get("source_pdf_bytes_sha_verified") is not False
        or refs.get("full_historical_pit_halt_calendar_verified") is not False
        or refs.get("first_publication_instant_authenticated") is not False
        or refs.get("historical_PIT_verified") is not False
        or refs.get("trading_allowed") is not False
        or refs.get("trade_gate")!="BLOCKED"
        or refs.get("orders")!=[] or refs.get("executable_candidates")!=[]):
        raise ValueError("unsafe P2/P3 provenance or false official PIT promotion")
    missing=queue.get("missing_official_halt_source_research_queue")
    cases=refs.get("cases")
    if not isinstance(missing,list) or not isinstance(cases,list) or len(missing)!=8 or len(cases)!=8:
        raise ValueError("not exactly eight pending issuer cases")
    indexed={}
    for x in missing:
        if not isinstance(x,dict) or x.get("issuer") in indexed:
            raise ValueError("duplicate live issuer")
        indexed[x.get("issuer")]=x
    if set(indexed)!=set(EXPECTED):
        raise ValueError("live source issuer membership changed")
    found={};document_total=0;pdf_count=0;reprint_count=0
    for case in cases:
        if not isinstance(case,dict) or case.get("issuer") not in EXPECTED or case["issuer"] in found:
            raise ValueError("unexpected issuer case")
        code=case["issuer"]
        shard,sha,halt,resume,st_day=EXPECTED[code]
        prior=indexed[code]
        if (case.get("shard_id")!=shard or case.get("original_csv_sha256")!=sha
            or prior.get("shard_id")!=shard or prior.get("original_csv_sha256")!=sha
            or case.get("claimed_halt_start")!=halt or case.get("claimed_resume_day")!=resume
            or case.get("st_removal_effective_day")!=st_day
            or case.get("source_pdf_bytes_sha_verified") is not False
            or case.get("full_pit_tradability_verified") is not False
            or case.get("gap_resolved") is not False
            or case.get("feature_shard_promotion_authorized") is not False):
            raise ValueError("changed source original or misleading status dates")
        docs=case.get("documents")
        if not isinstance(docs,list) or not 1<=len(docs)<=3:
            raise ValueError("missing issuer references")
        kinds=set()
        for document in docs:
            if not isinstance(document,dict) or document.get("kind") in kinds:
                raise ValueError("duplicate reference kind")
            kinds.add(document["kind"])
            cls=document.get("reference_class")
            url=document.get("url")
            if (cls not in ("issuer_pdf_indexed","publisher_reprint") or not isinstance(url,str)
                or document.get("content_sha256") is not None
                or document.get("first_publication_instant_authenticated") is not False):
                raise ValueError("unverified PDF bytes misrepresented")
            parsed=urlsplit(url)
            if parsed.scheme!="https" or parsed.username or parsed.password or parsed.fragment:
                raise ValueError("invalid disclosure URL")
            if cls=="issuer_pdf_indexed":
                if (parsed.netloc!="static.cninfo.com.cn" or parsed.query
                    or not PDF_PATH.fullmatch(parsed.path)):
                    raise ValueError("untrusted issuer PDF reference")
                pdf_count+=1
            elif parsed.netloc not in ("paper.cnstock.com","epaper.cs.com.cn","vip.stock.finance.sina.com.cn"):
                raise ValueError("non-whitelisted publisher reprint")
            else:reprint_count+=1
            if not re.fullmatch(r"2026-(09|10)-\d{2}",document.get("date","")):
                raise ValueError("announcement publication date invalid")
            if not isinstance(document.get("announcement"),str) or not document["announcement"]:
                raise ValueError("missing issuer announcement identifier")
            document_total+=1
        if st_day and (not isinstance(case.get("unresolved_caveat"),str)
                       or "ST" not in case["unresolved_caveat"]):
            raise ValueError("historical ST exclusion warning missing")
        found[code]={"issuer":code,"shard":shard,
            "original_csv_sha256":sha,"halt_start_research_claim":halt,
            "resume_day_research_claim":resume,
            "st_removal_day_research_claim":st_day,
            "reference_count":len(docs),
            "pdf_bytes_sha_independently_verified":False,
            "full_historical_pit_verified":False,
            "feature_gap_resolved":False}
    if set(found)!=set(EXPECTED):
        raise ValueError("incomplete issuer set")
    return {"phase":PHASE,"source_epoch_sha256":EPOCH,
        "research_issuer_reference_count":len(found),
        "new_research_reference_documents":document_total,
        "issuer_pdf_url_references":pdf_count,
        "publisher_reprint_references":reprint_count,
        "legacy_research_reference_issuer_count":7,
        "combined_research_reference_issuer_count":15,
        "still_missing_a_research_link_issuer_count":0,
        "pdf_original_bytes_sha_independently_verified_count":0,
        "official_full_pit_halt_certified_count":0,
        "original_feature_gap_issuers_unresolved":16,
        "original_feature_gap_shards_unresolved":15,
        "P2_feature_shards_promoted":0,"P3_offline_engineering_acceptance_automatically_changed":False,
        "historical_ST_exclusion_requires_effective_date":True,
        "results":[found[k] for k in sorted(found)],
        "historical_PIT_verified":False,"trade_gate":"BLOCKED",
        "orders":[],"executable_candidates":[],"original_archive_writer_change_authorized":False}
def main():
    p=argparse.ArgumentParser()
    for name in ("queue","sources","out"):
        p.add_argument("--"+name,required=True,type=Path)
    a=p.parse_args()
    result=reconcile(json.loads(a.queue.read_text()),json.loads(a.sources.read_text()))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print("P3_EIGHT_ISSUERS_DISCLOSURE_RESEARCH_LINKS_RECONCILED",
          json.dumps({k:result[k] for k in (
             "combined_research_reference_issuer_count",
             "issuer_pdf_url_references",
             "publisher_reprint_references",
             "original_feature_gap_shards_unresolved","trade_gate")}))
if __name__=="__main__":main()
