"""Read-only triage of frozen refresh artifact; vendor status is not PIT proof."""
import argparse,csv,hashlib,io,json,re,zipfile
from pathlib import Path

def triage(raw,expected_sha,expected_count):
    if hashlib.sha256(raw).hexdigest()!=expected_sha:raise ValueError("artifact SHA mismatch")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        names=z.namelist()
        if len(names)!=len(set(names)):raise ValueError("duplicate artifact members")
        report=json.loads(z.read("p2-refresh-aggregate.json"))
        if report["trade_gate"]!="BLOCKED" or report["orders"]!=[] or report["executable_candidates"]!=[] or report["historical_PIT_verified"] is not False or report["target_asof"]!="2026-11-25":
            raise ValueError("unsafe or wrong cutoff")
        rows=report["results"]
        if len(rows)!=expected_count or report["accepted_issuers"]!=expected_count or len({r["code"] for r in rows})!=expected_count:raise ValueError("wrong scope")
        output=[]
        for r in rows:
            if r["recovered_at_new_cutoff"] is True:continue
            code=r["code"]
            if not re.fullmatch(r"(?:sh\.60[0-5]|sz\.00[0-3])[0-9]{3}",code):raise ValueError("invalid code")
            filename=code.replace(".","_")+".csv"
            matches=[n for n in names if re.fullmatch(r"p2-batch_[0-9]{4}/"+re.escape(filename),n) or re.fullmatch(r"p2-batch-[0-9]{4}/"+re.escape(filename),n)]
            if len(matches)!=1:raise ValueError("ambiguous raw source")
            data=z.read(matches[0])
            if hashlib.sha256(data).hexdigest()!=r["extension_sha256"]:raise ValueError("extension SHA mismatch")
            bars=list(csv.DictReader(data.decode("utf-8-sig").splitlines()))
            days=[b["date"] for b in bars]
            if len(days)!=r["new_vendor_rows"] or days!=sorted(set(days)) or any(b["code"]!=code or b["tradestatus"] not in ("0","1") for b in bars):raise ValueError("invalid bars")
            if not days or days[-1]!=r["latest_observed_day"]:raise ValueError("cutoff mismatch")
            trailing=0
            for b in reversed(bars):
                if b["tradestatus"]!="1":break
                trailing+=1
            if trailing!=r["trailing_tradable_observations"]:raise ValueError("streak mismatch")
            output.append(dict(issuer=code,source_member=matches[0],extension_sha256=r["extension_sha256"],
                 vendor_nontradable_days=[b["date"] for b in bars if b["tradestatus"]=="0"],
                 trailing_tradable_observations=trailing,additional_consecutive_observations_needed=max(0,21-trailing),
                 missing_expected_sessions=r["missing_expected_sessions"],official_notice_verified=False,
                 official_first_publication_verified=False,task="AUTHENTICATE_HALT_RESUME_AND_EFFECTIVE_INTERVAL"))
        if len(output)!=report["research_gap_issuers"]:raise ValueError("gap count mismatch")
    return dict(source_artifact_sha256=expected_sha,asof=report["target_asof"],accepted_issuers=expected_count,
                gap_issuers=len(output),official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],tasks=output)

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("--artifact",type=Path,required=True);p.add_argument("--sha256",required=True);p.add_argument("--count",type=int,required=True);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();r=triage(a.artifact.read_bytes(),a.sha256,a.count);a.out.write_text(json.dumps(r,indent=2)+"\n")
    print("P3_REFRESH_GAP_TRIAGE:",json.dumps(r))
