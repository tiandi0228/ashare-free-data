"""Frozen 19-issuer evidence ledger; independent byte checks, no PIT promotion."""
import argparse,hashlib,json,zipfile,re
from pathlib import Path
from collector.p3_next_originals import safe
PIN="1e854608d0b3c2cacec803f8087ecfee39af1dea9166a6709d83a6a553995a2c"
GROUPS=(
 ("p3-pinned-originals",4,"pdf_sha256"),
 ("p3-additional-originals",2,"source_sha256"),
 ("p3-next-originals",3,"source_sha256"),
 ("p3-resume-originals",4,"source_sha256"),
 ("p3-final-gap-leads",2,"source_sha256"),
)
def sha(raw):return hashlib.sha256(raw).hexdigest()
def verified_pdf(raw,expected):
    if not re.fullmatch(r"[0-9a-f]{64}",expected) or not raw.startswith(b"%PDF-") or len(raw)>20000000 or sha(raw)!=expected:raise ValueError("PDF byte mismatch")
def index_tasks(queue):
    safe(queue)
    by={r["issuer"]:r for r in queue["tasks"]}
    if len(by)!=19 or len(queue["tasks"])!=19:raise ValueError("wrong scope")
    return by
def build(archive,queue,root):
    by=index_tasks(queue)
    if sha(archive.read_bytes())!=PIN:raise ValueError("archive mismatch")
    root.mkdir(parents=True,exist_ok=True);records={}
    with zipfile.ZipFile(archive) as z:
        if len(z.namelist())!=len(set(z.namelist())):raise ValueError("duplicate members")
        old=json.loads(z.read("p3-refresh-gap-triage.json"));safe(old)
        if old!=queue:raise ValueError("queue mismatch")
        for group,count,hashkey in GROUPS:
            report=json.loads(z.read(group+".json"));safe(report)
            verified=0
            for r in report["records"]:
                issuer=r["issuer"]
                if issuer not in by or issuer in records or r["extension_sha256"]!=by[issuer]["extension_sha256"]:raise ValueError("issuer provenance mismatch")
                if r.get("official_certified") is not False or r.get("first_publication_verified") is not False:raise ValueError("unexpected certification")
                is_verified=r["official_original_verified"]
                if type(is_verified) is not bool:raise ValueError("invalid verification flag")
                item=dict(issuer=issuer,extension_sha256=by[issuer]["extension_sha256"],vendor_nontradable_days=by[issuer]["vendor_nontradable_days"],missing_expected_sessions=by[issuer]["missing_expected_sessions"],evidence_report=group+".json",evidence_report_sha256=sha(z.read(group+".json")),official_original_verified=is_verified,first_publication_verified=False,full_interval_verified=False,official_certified=False,eligible_for_trading=False)
                if is_verified:
                    filename=r.get("file",issuer+".pdf")
                    if filename!=issuer+".pdf":raise ValueError("unexpected filename")
                    folder="p3-final-gap-originals" if group=="p3-final-gap-leads" else group
                    raw=z.read(folder+"/"+filename);verified_pdf(raw,r[hashkey])
                    (root/filename).write_bytes(raw)
                    item.update(pdf_sha256=r[hashkey],file=filename,status="ORIGINAL_BYTES_VERIFIED")
                    verified+=1
                else:
                    if group!="p3-final-gap-leads" or not r.get("public_lead_url"):raise ValueError("missing lead")
                    item.update(status="PUBLIC_LEAD_ONLY",public_lead_url=r["public_lead_url"])
                for k in ("url","kind","notice_halt_start","notice_resume","notice_st_effective","notice_st_removed_effective","notice_limit_pct","notice_start","notice_resume_lead"):
                    if k in r:item[k]=r[k]
                records[issuer]=item
            if verified!=count:raise ValueError("group count mismatch")
    if set(records)!=set(by):raise ValueError("incomplete ledger")
    n=sum(r["official_original_verified"] for r in records.values())
    if n!=15:raise ValueError("wrong original count")
    return dict(asof=queue["asof"],source_archive_sha256=PIN,gap_issuers=19,public_lead_coverage=19,original_issuers_verified=n,remaining_original_gaps=sorted(c for c,r in records.items() if not r["official_original_verified"]),issuer_network_calls=0,official_certified=0,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[],records=[records[c] for c in sorted(records)])
if __name__=="__main__":
    p=argparse.ArgumentParser()
    for x in ("archive","queue","root","out"):p.add_argument("--"+x,type=Path,required=True)
    a=p.parse_args();r=build(a.archive,json.loads(a.queue.read_bytes()),a.root);a.out.write_text(json.dumps(r,indent=2)+"\n");print("P3_UNIFIED_LEDGER:",json.dumps({k:v for k,v in r.items() if k!="records"}))
