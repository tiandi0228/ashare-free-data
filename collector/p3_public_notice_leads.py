"""Persist independently discovered public notice leads without promoting them to PIT."""
import argparse,json
from pathlib import Path
LEADS={
"sh.600185":dict(start="2026-11-12",resume="2026-11-26",kind="MAJOR_RESTRUCTURING",urls=["https://vip.stock.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?CompanyCode=10000146&gather=1&id=12724590","https://www.sse.com.cn/assortment/stock/list/info/company/index.shtml?COMPANY_CODE=600185"],notice_number="2026-073",source_status="EXCHANGE_INDEX_AND_MIRROR_LEAD"),
"sh.600567":dict(start="2026-11-19",resume="2026-11-26",kind="MAJOR_MATTER",urls=["https://epaper.cs.com.cn/zgzqb/html/2026-11/19/nw.D110000zgzqb_20261119_6-B049.htm","https://epaper.cs.com.cn/zgzqb/html/2026-11/21/nw.D110000zgzqb_20261121_1-B022.htm","https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12723758&stockid=600567"],notice_number="2026-075",source_status="NEWSPAPER_AND_MIRROR_LEAD"),
"sh.603595":dict(start="2026-11-25",resume="2026-11-26",kind="REMOVE_OTHER_RISK_WARNING",urls=["https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12721625&stockid=603595"],notice_number="2026-053",source_status="MIRROR_LEAD"),
"sz.000820":dict(start="2026-11-25",resume="2026-11-26",kind="ADD_OTHER_RISK_WARNING",urls=["https://finance.sina.com.cn/stock/s/2026-11-25/doc-inizwwnp9684162.shtml"],notice_number=None,source_status="NEWS_SUMMARY_LEAD"),
}
def build(queue,bridge):
    for r in (queue,bridge):
        if r["trade_gate"]!="BLOCKED" or r["orders"]!=[] or r["executable_candidates"]!=[] or r["official_certified"]!=0 or r["historical_PIT_verified"] is not False or r["asof"]!="2026-11-25":raise ValueError("unsafe source")
    by={t["issuer"]:t for t in queue["tasks"]}
    if len(by)!=19 or len(queue["tasks"])!=19 or bridge["retrospective_notice_supported"]!=2:raise ValueError("wrong scope")
    done={r["issuer"] for r in bridge["records"]}
    if done!={"sz.002717","sz.002731"}:raise ValueError("wrong bridge")
    results=[]
    for c,r in LEADS.items():
        t=by[c];days=t["vendor_nontradable_days"]
        if not days or days[0]!=r["start"] or days[-1]!="2026-11-25" or r["resume"]<=queue["asof"] or t["missing_expected_sessions"]:raise ValueError("lead does not align with cutoff")
        results.append(dict(issuer=c,**r,vendor_days=days,extension_sha256=t["extension_sha256"],official_original_verified=False,first_publication_verified=False,resume_vendor_observed=False,official_certified=False))
    return dict(asof=queue["asof"],gap_issuers=19,original_notice_supported=2,additional_public_leads=len(results),unmatched_issuers=sorted(set(by)-done-set(LEADS)),official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=results)
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("queue","bridge","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=build(json.loads(a.queue.read_bytes()),json.loads(a.bridge.read_bytes()));a.out.write_text(json.dumps(r,indent=2)+"\n");print("P3_PUBLIC_NOTICE_LEADS:",json.dumps(r))
