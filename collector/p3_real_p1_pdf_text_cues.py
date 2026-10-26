"""Extract issuer-linked event research cues from independently replayed real P1 PDFs.
Text presence is not an effective-date or historical publication certification.
"""
import argparse,json,re
from pathlib import Path
from pypdf import PdfReader
from collector.p3_real_p1_pdf_replay import audit

KEYWORDS=("停牌","复牌","退市","风险警示","上市","特别处理")
DATE=re.compile(r"20\d{2}年\s*(?:1[0-2]|[1-9])月\s*(?:3[01]|[12]\d|[1-9])日")

def extract(root):
    root=Path(root);proof=audit(root)
    receipt=json.loads((root/"quality.json").read_text())
    results=[]
    for row in receipt["sources"]:
        item={"issuer":row["issuer"],"announcement_id":row["announcement_id"],
              "original_sha256":row.get("sha256"),"text_status":"UNAVAILABLE_NOT_NO_RISK",
              "event_effective_date_certified":False,"publication_time_certified":False,
              "historical_PIT_verified":False}
        if row.get("original_bytes_verified") is True:
            file=root/row["original_file"]
            reader=PdfReader(str(file),strict=True)
            if len(reader.pages)>80:raise ValueError("too many source pages")
            text="".join((p.extract_text() or "") for p in reader.pages)
            normalized="".join(text.split())
            item.update(text_status="TEXT_EXTRACTED_RESEARCH_ONLY" if normalized else "NO_EXTRACTABLE_TEXT",
                        issuer_code_in_text=row["issuer"][-6:] in normalized,
                        event_keyword_presence={k:k in normalized for k in KEYWORDS},
                        date_text_candidates=sorted(set(DATE.findall(normalized)))[:30])
        results.append(item)
    return {"phase":"P3_REAL_P1_PDF_TEXT_RESEARCH_CUES",
            "independently_replayed_originals":proof["independently_sha_verified"],
            "source_count":len(results),"sources":results,
            "event_effective_dates_certified":0,"historical_PIT_verified":False,
            "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--root",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();r=extract(a.root);d=Path(a.out);d.parent.mkdir(parents=True,exist_ok=True)
    d.write_text(json.dumps(r,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({"phase":r["phase"],"source_count":r["source_count"],
                      "statuses":[s["text_status"] for s in r["sources"]],"historical_PIT_verified":False},ensure_ascii=False))
if __name__=="__main__":main()
