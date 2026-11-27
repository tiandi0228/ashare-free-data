"""Single bounded batch observation; no schedule, broker, or archive writes."""
import argparse,csv,hashlib,io,json,re,time
from pathlib import Path
from collector.p2_refresh_checkpoint import reconcile
from collector.p2_gap_extension_replay import START,END,inspect
from collector.p2_independent_bars import FIELDS
from collector.p2_refresh_batch_replay import verify,checked_bytes

class ProviderResponseError(ValueError):
    def __init__(self,stage,error_code,schema_mismatch):
        self.stage=stage
        self.error_code=str(error_code)[:32]
        self.schema_mismatch=schema_mismatch
        super().__init__("provider response rejected")

def query_once(client,code):
    q=client.query_history_k_data_plus(code,fields=",".join(FIELDS),start_date=START,end_date=END,frequency="d",adjustflag="3")
    if q.error_code!="0" or list(q.fields)!=FIELDS:raise ProviderResponseError("query",q.error_code,list(q.fields)!=FIELDS)
    rows=[]
    while q.next():
        r=list(q.get_row_data())
        if len(r)!=len(FIELDS) or not all(isinstance(x,str) for x in r):raise ValueError("invalid vendor row")
        rows.append(r)
        if len(rows)>36:raise ValueError("unbounded response")
    if q.error_code!="0" or not rows:raise ProviderResponseError("iteration",q.error_code,False)
    return rows

def query_with_retry(client,code,index,sleep=time.sleep):
    for attempt in range(1,4):
        try:
            return query_once(client,code)
        except ProviderResponseError as e:
            print("P2_PROVIDER_REJECT:",json.dumps(dict(batch_index=index,issuer=code,attempt=attempt,stage=e.stage,error_code=e.error_code,schema_mismatch=e.schema_mismatch)),flush=True)
            if attempt==3:raise
            sleep(5*attempt)
    raise AssertionError("unreachable")

def observe(manifest,index,root,out,client):
    reconcile(manifest,[])
    if root.name!=manifest["epoch"][:16] or type(index) is not int or not 0<=index<len(manifest["batches"]):
        raise ValueError("invalid bounded scope")
    batch=manifest["batches"][index]
    originals={}
    for row in batch["issuers"]:
        if not re.fullmatch(r"shard_[0-9]{4}",row["source_shard"]):raise ValueError("invalid shard")
        code=row["code"]
        originals[code]=checked_bytes(root/row["source_shard"]/(code.replace(".","_")+".csv"),row["original_csv_sha256"])
    out.mkdir(parents=True,exist_ok=False)
    results=[]
    if client.login().error_code!="0":raise ValueError("provider login failed")
    try:
        for row in batch["issuers"]:
            code=row["code"]
            rows=query_with_retry(client,code,index)
            stream=io.StringIO(newline="")
            writer=csv.writer(stream,lineterminator="\n")
            writer.writerow(FIELDS);writer.writerows(rows)
            raw=stream.getvalue().encode()
            d=inspect(originals[code],raw,code)
            (out/(code.replace(".","_")+".csv")).write_bytes(raw)
            results.append(dict(code=code,original_csv_sha256=row["original_csv_sha256"],extension_sha256=hashlib.sha256(raw).hexdigest(),status="FEATURE_WINDOW_OBSERVED" if d["recovered_at_new_cutoff"] else "VENDOR_WINDOW_GAP",research_features=d["research_features"]))
    finally:client.logout()
    receipt=dict(epoch=manifest["epoch"],batch_index=index,manifest_sha256=batch["manifest_sha256"],asof=END,results=results,historical_PIT_verified=False,trade_gate="BLOCKED",orders=[],executable_candidates=[])
    replay=verify(manifest,receipt,root,out)
    (out/"receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")
    (out/"replay.json").write_text(json.dumps(replay,indent=2)+"\n")
    return replay

if __name__=="__main__":
    p=argparse.ArgumentParser()
    for arg in ("manifest","archive-epoch","out"):p.add_argument("--"+arg,type=Path,required=True)
    p.add_argument("--batch-index",type=int,required=True)
    a=p.parse_args()
    import baostock
    r=observe(json.loads(a.manifest.read_bytes()),a.batch_index,a.archive_epoch,a.out,baostock)
    print("P2_BOUNDED_BATCH:",json.dumps({k:v for k,v in r.items() if k!="results"}))
