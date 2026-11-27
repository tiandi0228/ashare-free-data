"""Vendor-only daily flat-bar flags; no inference of security-specific official limits."""
import argparse,csv,hashlib,json,re,zipfile
from collections import Counter
from decimal import Decimal as D,ROUND_HALF_UP
from pathlib import Path
from collector.p2_independent_bars import audit_csv
from collector.p4_curated_session_exit import sessions_between
SHA="29c314f023379729e5308b805a0ecd35188eccbdaeed4046387b7a2e1d35981d"
def flags(rows):
    output=[]
    for a,b in zip(rows,rows[1:]):
        if a["tradestatus"]!="1" or b["tradestatus"]!="1":continue
        if sessions_between(a["date"],b["date"])!=[a["date"],b["date"]]:continue
        if D(a["volume"])<=0 or D(b["volume"])<=0:continue
        prices=[D(b[k]) for k in ("open","high","low","close")]
        if len(set(prices))!=1:continue
        prev=D(a["close"]);price=prices[0]
        hypotheses=[]
        for band in (D(".05"),D(".10")):
            for side,sign in (("UP",1),("DOWN",-1)):
                assumed=(prev*(1+sign*band)).quantize(D(".01"),rounding=ROUND_HALF_UP)
                if price==assumed:hypotheses.append(dict(side=side,assumed_band_pct=str(band*100)))
        output.append(dict(code=b["code"],day=b["date"],prior_day=a["date"],prior_vendor_close=str(prev),flat_vendor_price=str(price),hypotheses=hypotheses,official_limit_verified=False,fill_verified=False))
    return output

def audit(path):
    if hashlib.sha256(path.read_bytes()).hexdigest()!=SHA:raise ValueError("wrong frozen artifact")
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError("duplicate members")
        report=json.loads(z.read("p2-refresh-aggregate.json"))
        if report["target_asof"]!="2026-11-25" or report["accepted_issuers"]!=3194 or report["full_universe_observed"] is not True or report["trade_gate"]!="BLOCKED" or report["orders"]!=[] or report["executable_candidates"]!=[] or report["historical_PIT_verified"] is not False:raise ValueError("unsafe scope")
        by={r["code"]:r for r in report["results"]}
        if len(by)!=3194:raise ValueError("duplicate issuer")
        seen=set();records=[];counts=Counter()
        for n in names:
            m=re.fullmatch(r"p2-batch-[0-9]{4}/((?:sh_60[0-5]|sz_00[0-3])[0-9]{3})\.csv",n)
            if not m:continue
            code=m.group(1).replace("_",".")
            if code in seen or code not in by:raise ValueError("invalid scope")
            seen.add(code);raw=z.read(n);sha=hashlib.sha256(raw).hexdigest()
            if sha!=by[code]["extension_sha256"]:raise ValueError("raw hash mismatch")
            audit_csv(raw,code)
            rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
            if rows[0]["date"]<"2026-10-21" or rows[-1]["date"]>"2026-11-25":raise ValueError("wrong window")
            counts["vendor_rows"]+=len(rows)
            counts["active_rows"]+=sum(r["tradestatus"]=="1" for r in rows)
            for r in flags(rows):
                r["extension_sha256"]=sha
                records.append(r)
                counts["flat_active_adjacent_observations"]+=1
                if r["hypotheses"]:counts["hypothetical_band_matches"]+=1
                else:counts["flat_other"]+=1
        if seen!=set(by):raise ValueError("incomplete scope")
    return dict(asof="2026-11-25",issuer_count=len(seen),source_artifact_sha256=SHA,counts=dict(counts),affected_issuers=len({r["code"] for r in records if r["hypotheses"]}),official_limit_certified=0,corporate_actions_verified=False,historical_ST_verified=False,official_calendar_verified=False,historical_PIT_verified=False,execution_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=records)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--artifact",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();r=audit(a.artifact);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P4_FLAT_BAR_RISK:",json.dumps({k:v for k,v in r.items() if k!="records"}))
