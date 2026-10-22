"""Deterministically create a bounded, reproducible research shard manifest from vendor roster rows."""
import argparse, hashlib, json, re
from collections import defaultdict
from pathlib import Path

CODE=re.compile(r"^(?:sh\.(?:600|601|603|605)|sz\.(?:000|001|002|003))[0-9]{3}$")
MAX=128
BUCKETS=("sh.600","sh.601","sh.603","sh.605","sz.000","sz.001","sz.002","sz.003")
def select_roster(rows, maximum=MAX):
    if not isinstance(rows,list) or type(maximum) is not int or not 1<=maximum<=MAX:
        raise ValueError("invalid roster input/cap")
    all_codes=set()
    for item in rows:
        if not isinstance(item,dict) or not isinstance(item.get("code"),str):
            raise ValueError("invalid roster item")
        code=item["code"]
        if code in all_codes:
            raise ValueError("duplicate vendor roster code")
        all_codes.add(code)
    selected=sorted(c for c in all_codes if CODE.fullmatch(c))
    if not selected:
        raise ValueError("empty mainboard sample")
    groups=defaultdict(list)
    for code in selected:
        groups[code[:6]].append(code)
    ordered=[]
    idx=0
    while len(ordered)<maximum and len(ordered)<len(selected):
        for bucket in BUCKETS:
            if idx<len(groups[bucket]) and len(ordered)<maximum:
                ordered.append(groups[bucket][idx])
        idx+=1
    selected=ordered
    content="".join(c+"\n" for c in selected)
    return content,{"phase":"P1_VENDOR_ROSTER_RESEARCH_MANIFEST",
                    "selected_count":len(selected),"candidate_mainboard_count":sum(bool(CODE.fullmatch(c)) for c in all_codes),
                    "selection":"deterministic prefix-stratified round-robin from retrospective roster (NOT historical PIT universe)",
                    "prefix_counts":{k:sum(x.startswith(k) for x in selected) for k in BUCKETS},
                    "manifest_sha256":hashlib.sha256(content.encode()).hexdigest(),
                    "official_historical_membership_verified":False,
                    "historical_asof_verified":False,
                    "trade_gate":"BLOCKED","orders":[],"executable_candidates":[]}
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--roster-json",required=True)
    ap.add_argument("--manifest",required=True)
    ap.add_argument("--receipt",required=True)
    ap.add_argument("--limit",type=int,default=128)
    a=ap.parse_args()
    source=json.loads(Path(a.roster_json).read_text())
    content,receipt=select_roster(source,a.limit)
    Path(a.manifest).parent.mkdir(parents=True,exist_ok=True)
    Path(a.manifest).write_text(content)
    Path(a.receipt).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(receipt))
if __name__=="__main__":main()
