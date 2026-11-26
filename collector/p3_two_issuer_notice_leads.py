"""Two issuer notice leads; keep publisher originals and mirrors distinct."""
import argparse,hashlib,json,re,subprocess
from pathlib import Path
from urllib.request import urlopen

SOURCES=[
("sh.603159","2026-09-10","CNINFO","https://static.cninfo.com.cn/finalpage/2026-09-10/1225555538.PDF",r"2026年9月10日.{0,25}开市起停牌"),
("sh.603159","2026-06-17","MIRROR","https://stockmc.xueqiu.com/202606/603159_20260623_8TSH.pdf",r"2026年6月17日.{0,25}开市起继续停牌"),
("sh.601010","2026-04-29","MIRROR","https://pdf.dfcfw.com/pdf/H2_AN202604281821684941_1.pdf",r"2026年4月29日.{0,20}停牌1天"),
("sh.601010","2026-05-08","EXCHANGE_REPORT_VIA_CNINFO","https://dataclouds.cninfo.com.cn/sjother2/regulatory/2026/20260508/6bbb027c595b4c599d0a8988749dad27.pdf",r"601010.{0,60}2026-05-08.{0,40}全天"),
]
def run(queue,out):
    if queue["trade_gate"]!="BLOCKED" or queue["orders"]!=[] or queue["executable_candidates"]!=[]:
        raise ValueError("unsafe queue")
    tasks={t["code"]:t for t in queue["tasks"]}
    out.mkdir(parents=True,exist_ok=False)
    receipts=[]
    for code,day,source,url,pattern in SOURCES:
        target=next(t for t in tasks[code]["targets"] if t["target_date"]==day)
        r=dict(code=code,target=target,source=source,url=url,verified=False,first_publication_authenticated=False)
        try:
            with urlopen(url,timeout=35) as response:
                if response.geturl()!=url:raise ValueError("redirect")
                raw=response.read(8388609)
            if not raw.startswith(b"%PDF-") or len(raw)>8388608:raise ValueError("invalid PDF")
            p=out/(code+"-"+day+".pdf")
            p.write_bytes(raw)
            text=re.sub(r"\s+","",subprocess.check_output(["pdftotext","-layout",str(p),"-"],text=True,timeout=20))
            if code[3:] not in text or not re.search(pattern,text):raise ValueError("date phrase mismatch")
            r.update(verified=True,sha256=hashlib.sha256(raw).hexdigest(),filename=p.name)
        except (OSError,ValueError,subprocess.SubprocessError) as e:
            r.update(error=type(e).__name__,detail=str(e)[:200])
        receipts.append(r)
    return dict(receipts=receipts,official_channel_matches=sum(r["verified"] and r["source"]!="MIRROR" for r in receipts),
                mirror_matches=sum(r["verified"] and r["source"]=="MIRROR" for r in receipts),
                complete_original_pairs=0,officially_certified_halt_dates=0,historical_PIT_verified=False,
                trade_gate="BLOCKED",orders=[],executable_candidates=[])

if __name__=="__main__":
    p=argparse.ArgumentParser();p.add_argument("queue",type=Path);p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();r=run(json.loads(a.queue.read_bytes()),a.out)
    (a.out/"report.json").write_text(json.dumps(r,indent=2)+"\n")
    print("TWO_ISSUER_NOTICE_LEADS:",json.dumps({k:v for k,v in r.items() if k!="receipts"}))
