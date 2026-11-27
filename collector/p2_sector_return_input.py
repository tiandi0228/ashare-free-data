"""Rebuild sector return inputs from fixed original vendor CSVs, not current membership."""
import argparse,csv,hashlib,json,re,zipfile
from decimal import Decimal as D
from pathlib import Path
from collector.p2_independent_bars import audit_csv
from collector.p4_curated_session_exit import sessions_between

ASOF="2026-11-25"
ARTIFACT_SHA="29c314f023379729e5308b805a0ecd35188eccbdaeed4046387b7a2e1d35981d"
def digest(b):return hashlib.sha256(b).hexdigest()

def return_window(raw,code):
    audit_csv(raw,code)
    rows=list(csv.DictReader(raw.decode("utf-8-sig").splitlines()))
    if rows[-1]["date"]>ASOF:raise ValueError("future data")
    recent=rows[-21:]
    if len(recent)!=21 or recent[-1]["date"]!=ASOF or [r["date"] for r in recent]!=sessions_between(recent[0]["date"],ASOF) or any(r["tradestatus"]!="1" or D(r["volume"])<=0 for r in recent):
        return dict(code=code,asof=ASOF,window_verified=False,return20_pct=None)
    value=(D(recent[-1]["close"])/D(recent[0]["close"])-1)*100
    return dict(code=code,asof=ASOF,window_verified=True,return20_pct=str(value.quantize(D(".0001"))))

def build(path):
    if digest(path.read_bytes())!=ARTIFACT_SHA:raise ValueError("artifact SHA mismatch")
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError("duplicate members")
        report=json.loads(z.read("p2-refresh-aggregate.json"))
        if report["target_asof"]!=ASOF or report["accepted_issuers"]!=3194 or report["full_universe_observed"] is not True or report["historical_PIT_verified"] is not False or report["trade_gate"]!="BLOCKED" or report["orders"]!=[] or report["executable_candidates"]!=[]:raise ValueError("unsafe scope")
        by={r["code"]:r for r in report["results"]}
        if len(by)!=3194:raise ValueError("duplicate issuer")
        raw_members={}
        for n in names:
            m=re.fullmatch(r"p2-batch-[0-9]{4}/((?:sh_60[0-5]|sz_00[0-3])[0-9]{3})\.csv",n)
            if not m:continue
            code=m.group(1).replace("_",".")
            if code in raw_members:raise ValueError("duplicate raw issuer")
            raw_members[code]=n
        if set(raw_members)!=set(by):raise ValueError("wrong raw scope")
        rows=[]
        for c in sorted(by):
            raw=z.read(raw_members[c])
            if digest(raw)!=by[c]["extension_sha256"]:raise ValueError("raw SHA mismatch")
            r=return_window(raw,c)
            r["extension_sha256"]=digest(raw)
            rows.append(r)
    return dict(asof=ASOF,universe=sorted(by),membership=[],returns=rows,source_artifact_sha256=ARTIFACT_SHA,corporate_actions_verified=False,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[])

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--artifact",type=Path,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();r=build(a.artifact);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P2_SECTOR_RETURN_INPUT:",json.dumps(dict(issuers=len(r["universe"]),valid_returns=sum(x["window_verified"] for x in r["returns"]),membership_covered=0,trade_gate="BLOCKED")))
