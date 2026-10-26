"""Evidence-preserving local-clause review of real SHA-replayed P3 source PDFs.

A PDF may retrospectively state a dated event, but this is *not* proof
of independent first-publication instant or historical decision-time
availability. No unverified statement may create a trading state or order.
"""
import argparse,json,re
from datetime import datetime
from pathlib import Path

SHA=re.compile(r"[0-9a-f]{64}\Z")
DATE_RE=re.compile(r"20\d{2}年\s*\d{1,2}月\s*\d{1,2}日")
# Match a date and explicit action within the same short punctuation-bound clause.
EVENT_WORDS={
 "halt":{"HALT_START":r"停牌","RESUME_START":r"复牌"},
 "st":{"ST_APPLIED":r"(?:实施|被实施)(?:退市|其他)?风险警示",
       "ST_REMOVED":r"撤销(?:退市|其他)?风险警示"},
 "listing":{"LISTING_START":r"上市(?:交易)?"},
 "delisting":{"DELIST_EFFECTIVE":r"(?:终止上市|摘牌)"},
}
PREFIX=r"(?:自|于|从|将于)"
SEP=r"[^，,。；;！!？?\n]{0,18}"
EXCLUDE=re.compile(r"(?:拟|预计|计划|可能|尚未|不予|不会|否认|并非|如若|如果|假设)")
CLAUSE_SPLIT=re.compile(r"[，,。；;！!？?\n]")
MAX_LEADS=3000

def classify(text,day,kind):
    if not isinstance(text,str) or len(text)>200 or not isinstance(day,str):
        raise ValueError("invalid evidence text")
    if day not in text:raise ValueError("PDF date phrase not in claimed context")
    if not DATE_RE.fullmatch(day):raise ValueError("bad text date")
    choices=EVENT_WORDS.get(kind)
    if choices is None:raise ValueError("unsupported research event family")
    matched=[];ambiguous=0
    for clause in CLAUSE_SPLIT.split(text):
        if day not in clause:continue
        # Clauses mentioning multiple distinct dates are not one-to-one links.
        if len(set(DATE_RE.findall(clause)))!=1:
            ambiguous+=1;continue
        if EXCLUDE.search(clause):
            ambiguous+=1;continue
        for direction,word in choices.items():
            expr=PREFIX+re.escape(day)+SEP+r"(?:起|开市起|开盘起|开始)?"+SEP+word
            if re.search(expr,clause):
                matched.append((direction,clause))
    directions=set(x[0] for x in matched)
    if len(directions)==1:
        direction=next(iter(directions))
        return {"local_textual_direction_candidate":direction,
                "classification":"EXPLICIT_SAME_CLAUSE_TEXT_RESEARCH_ONLY",
                "source_clause_excerpt":next(c[:180] for d,c in matched if d==direction)}
    return {"local_textual_direction_candidate":None,
            "classification":"AMBIGUOUS_CONTEXT_REVIEW_REQUIRED" if ambiguous or len(directions)>1
                              else "NO_EXPLICIT_DATE_TO_EVENT_LOCAL_CLAUSE",
            "source_clause_excerpt":None}

def review(join,triage,pdf_text,originals,index):
    phases=(("P3_FULL_P1_OFFICIAL_SOURCE_SCOUT_RESEARCH",join),
            ("P3_REAL_P1_DATE_CONTEXT_TRIAGE",triage),
            ("P3_REAL_P1_PDF_TEXT_RESEARCH_CUES",pdf_text),
            ("P3_REAL_P1_INDEX_PDF_ORIGINAL_CAPTURE",originals),
            ("P3_REAL_P1_LIVE_INDEX_DISCOVERY",index))
    for phase,data in phases:
        if data.get("phase")!=phase or data.get("trade_gate")!="BLOCKED" or data.get("orders")!=[]:
            raise ValueError("invalid or unsafe evidence provenance")
    if (join.get("historical_PIT_verified") is not False
        or join.get("official_PIT_cells_certified")!=0
        or triage.get("historical_PIT_verified") is not False
        or pdf_text.get("historical_PIT_verified") is not False
        or originals.get("historical_PIT_verified") is not False
        or index.get("historical_PIT_verified") is not False
        or originals.get("retrieved")!=join.get("official_pdf_originals_sha_replayed")):
        raise ValueError("upstream evidence was promoted without provenance")
    leads=join.get("date_cue_leads")
    if not isinstance(leads,list) or len(leads)>MAX_LEADS or len(leads)!=join.get("research_issuer_day_date_cue_links"):
        raise ValueError("source linkage count mismatch")
    originals_by_key={}
    for row in originals.get("sources",[]):
        key=(row.get("issuer"),row.get("announcement_id"))
        if key in originals_by_key:raise ValueError("duplicate original")
        if row.get("original_bytes_verified") is True:
            if not SHA.fullmatch(row.get("sha256","")):
                raise ValueError("original PDF SHA missing")
            stamp=datetime.fromisoformat(row.get("observed_at_utc",""))
            if stamp.tzinfo is None:raise ValueError("PDF retrieval has no timezone")
        originals_by_key[key]=row
    text_by_key={}
    for item in pdf_text.get("sources",[]):
        key=(item.get("issuer"),item.get("announcement_id"))
        if key in text_by_key:raise ValueError("duplicate extracted PDF")
        if item.get("historical_PIT_verified") is not False:
            raise ValueError("false PDF text PIT claim")
        text_by_key[key]=item
    triaged={}
    for item in triage.get("candidate_contexts",[]):
        key=(item.get("issuer"),item.get("announcement_id"),item.get("original_sha256"),item.get("date_text"))
        if item.get("historical_publication_time_verified") is not False or item.get("historical_effective_date_verified") is not False:
            raise ValueError("unsupported time claim")
        triaged.setdefault(key,[]).append(item)
    index_by_key={}
    for row in index.get("results",[]):
        for cand in row.get("candidates",[]):
            key=(row["issuer"],cand.get("announcement_id"))
            if key in index_by_key:continue
            index_by_key[key]=cand
    output=[];seen=set()
    for lead in leads:
        key=(lead.get("issuer"),lead.get("announcement_id"))
        original=originals_by_key.get(key)
        pdf=text_by_key.get(key)
        if (original is None or original.get("original_bytes_verified") is not True
            or pdf is None or pdf.get("original_sha256")!=lead.get("pdf_sha256")
            or original.get("sha256")!=lead.get("pdf_sha256")
            or lead.get("historical_effective_date_authenticated") is not False
            or lead.get("historical_first_publication_utc_authenticated") is not False
            or lead.get("decision_day_trading_state_authenticated") is not False):
            raise ValueError("context not tied to same independently SHA-replayed original")
        identity=(key,lead.get("decision_day"),lead.get("kind"),lead.get("date_text"))
        if identity in seen:raise ValueError("duplicate same event research link")
        seen.add(identity)
        contexts=triaged.get((key[0],key[1],lead["pdf_sha256"],lead["date_text"]),[])
        if not contexts:raise ValueError("missing original contextual proof for linked date")
        # Distinct date contexts may refer to unrelated events; the upstream
        # link only depends on the ones that match its specific event family.
        cues={"halt":{"TRADING_HALT_CUE","TRADING_RESUME_CUE"},
              "st":{"ST_RISK_CUE"},"listing":{"LISTING_CUE"},
              "delisting":{"DELIST_CUE"}}.get(lead["kind"])
        if cues is None:raise ValueError("unknown source event family")
        relevant=[]
        for c in contexts:
            labels=c.get("candidate_event_cues",[])
            if not isinstance(labels,list):raise ValueError("bad original cue labels")
            if cues.intersection(labels):relevant.append(c)
        if not relevant:raise ValueError("no kind-matched original date context")
        checked=[classify(c["source_text_context"],lead["date_text"],lead["kind"]) for c in relevant]
        found={x["local_textual_direction_candidate"] for x in checked if x["local_textual_direction_candidate"]}
        issuer_in_text=pdf.get("issuer_code_in_text") is True
        if len(found)==1 and issuer_in_text:
            classification="LOCAL_ORIGINAL_DATE_ACTION_CANDIDATE_REVIEW_REQUIRED"
            direction=next(iter(found))
            clause=next(c["source_clause_excerpt"] for c in checked if c["local_textual_direction_candidate"]==direction)
        else:
            direction=None;clause=None
            classification=("PDF_ISSUER_CODE_NOT_IN_TEXT_REVIEW_REQUIRED" if not issuer_in_text else
                            "MULTIPLE_DATE_ACTION_DIRECTIONS_REVIEW_REQUIRED" if len(found)>1 else
                            "NO_EXPLICIT_DATE_EVENT_SENTENCE")
        idx=index_by_key.get(key,{})
        output.append({"issuer":key[0],"announcement_id":key[1],
            "decision_day":lead["decision_day"],"source_date_text":lead["date_text"],
            "candidate_kind":lead["kind"],"original_pdf_sha256":lead["pdf_sha256"],
            "original_retrieved_at_utc":original["observed_at_utc"],
            "index_publication_time_unverified":idx.get("index_published_milliseconds_unverified"),
            "pdf_issuer_code_in_text":issuer_in_text,
            "local_textual_direction_candidate":direction,"clause_excerpt":clause,
            "research_classification":classification,
            "historical_first_publication_authenticated":False,
            "historical_effective_date_authenticated":False,
            "complete_issuer_state_history_certified":False,
            "historical_asof_usable":False})
    return {"phase":"P3_P1_ORIGINAL_EFFECTIVE_CLAUSE_REVIEW",
        "evaluated_research_links":len(output),
        "explicit_original_clause_candidates":sum(bool(x["local_textual_direction_candidate"]) for x in output),
        "issuer_code_missing_links":sum(not x["pdf_issuer_code_in_text"] for x in output),
        "manual_review_only":output,
        "authenticated_first_publication_times":0,"certified_effective_dates":0,
        "official_PIT_cells_certified":0,"historical_PIT_verified":False,
        "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}

def main():
    p=argparse.ArgumentParser()
    for name in ("join","triage","pdf-text","originals","index","out"):
        p.add_argument("--"+name,required=True)
    a=p.parse_args()
    inputs=[json.loads(Path(getattr(a,name.replace("-","_"))).read_text())
            for name in ("join","triage","pdf-text","originals","index")]
    result=review(*inputs)
    path=Path(a.out);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps({key:value for key,value in result.items() if key!="manual_review_only"},ensure_ascii=False))
if __name__=="__main__":main()
