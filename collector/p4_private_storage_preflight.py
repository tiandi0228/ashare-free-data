"""Read-only source archive transfer manifest for private-storage migration."""
import argparse,hashlib,json
from pathlib import Path

def inventory(root):
    root=Path(root)
    receipts=sorted(root.glob("*/shard_*/quality.json"))
    if not receipts:raise ValueError("source receipts absent")
    objects=[]
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:continue
        raw=path.read_bytes()
        objects.append({"path":str(path.relative_to(root)),"size":len(raw),"sha256":hashlib.sha256(raw).hexdigest()})
    return {"phase":"P4_PRIVATE_STORAGE_MIGRATION_PREFLIGHT","objects":objects,
        "object_count":len(objects),"total_bytes":sum(x["size"] for x in objects),
        "source_receipt_count":len(receipts),"destination_written":False,
        "trade_gate":"BLOCKED"}
def main():
    p=argparse.ArgumentParser();p.add_argument("--source",required=True);p.add_argument("--out",required=True)
    a=p.parse_args();v=inventory(a.source);Path(a.out).parent.mkdir(parents=True,exist_ok=True)
    Path(a.out).write_text(json.dumps(v,indent=2)+"\n")
    print(json.dumps({k:v for k,v in v.items() if k!="objects"}))
if __name__=="__main__":main()
