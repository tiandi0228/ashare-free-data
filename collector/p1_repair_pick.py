"""Select a bounded archival repair shard; prefer backfill to new collection only when asked."""
import argparse,json
from pathlib import Path

def select_repair(report,ledger):
    if report.get("trade_gate")!="BLOCKED" or ledger.get("trade_gate")!="BLOCKED":
        raise ValueError("trade gate must remain blocked")
    done={row["index"] for row in ledger["completed"]}
    queue=report.get("archive_repair_queue",[])
    if queue!=sorted(set(queue)) or any(type(i) is not int or i not in done for i in queue):
        raise ValueError("invalid repair queue")
    return queue[0] if queue else None

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--audit",required=True);p.add_argument("--ledger",required=True)
    p.add_argument("--out",required=True)
    a=p.parse_args()
    index=select_repair(json.loads(Path(a.audit).read_text()),json.loads(Path(a.ledger).read_text()))
    dest=Path(a.out);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps({"repair_shard":index,"trade_gate":"BLOCKED"})+chr(10))
    print("REPAIR:",index if index is not None else "NONE")
if __name__=="__main__":main()
