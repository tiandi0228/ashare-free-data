"""Capture one unofficial Sina quote for P3 diagnostics only."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from urllib.request import HTTPRedirectHandler, Request, build_opener

from collector.p3_preauction_receipt import MAX_RAW, SHANGHAI, receipt

ORIGIN = "https://hq.sinajs.cn"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def build_result(raw, issuer, captured_at):
    if not re.fullmatch(r"(?:sh|sz)\.[0-9]{6}", issuer):
        raise ValueError("invalid issuer")
    symbol = issuer.replace(".", "")
    match = re.fullmatch(rb'var hq_str_' + symbol.encode() +
                         rb'="([^"\r\n]*)";\s*', raw)
    if not match or not match[1]:
        raise ValueError("missing or mismatched provider quote")
    fields = match[1].decode("gb18030").split(",")
    if len(fields) == 34 and fields[-1] == "":
        fields.pop()
    if len(fields) not in (32, 33) or not fields[0]:
        raise ValueError("unexpected quote layout")
    quote_time = None
    if fields[30] or fields[31]:
        date, clock = fields[30:32]
        if not (re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", date)
                and re.fullmatch(r"[0-9]{2}:[0-9]{2}:[0-9]{2}", clock)):
            raise ValueError("invalid provider quote clock")
        quote_time = datetime.fromisoformat(date + "T" + clock).replace(tzinfo=SHANGHAI)
    result = receipt(raw=raw, issuer=issuer, source_url=f"{ORIGIN}/list={symbol}",
                     source_time=quote_time.isoformat() if quote_time else None,
                     captured_at=captured_at, status="UNKNOWN",
                     mapping="Sina observed CSV layout: fields 30/31 quote clock; status unverified")
    result.update(provider="sina_unofficial", provider_status_raw=fields[32] if len(fields) == 33 else None,
                  source_clock_kind="provider_quote_timestamp", capture_clock_kind="local_utc_after_body_read")
    return result


def capture(issuer, *, opener=None):
    if not re.fullmatch(r"(?:sh|sz)\.[0-9]{6}", issuer):
        raise ValueError("invalid issuer")
    request = Request(f"{ORIGIN}/list={issuer.replace('.', '')}",
                      headers={"Referer": "https://finance.sina.com.cn/", "Cache-Control": "no-cache"})
    with (opener or build_opener(NoRedirect())).open(request, timeout=8) as response:
        if response.status != 200:
            raise ValueError("unexpected HTTP status")
        raw = response.read(MAX_RAW + 1)
        captured_at = datetime.now(timezone.utc).isoformat()
    if not 0 < len(raw) <= MAX_RAW:
        raise ValueError("invalid response size")
    return build_result(raw, issuer, captured_at)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("output exists")
    try:
        result = capture(args.issuer)
        with args.out.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    except (OSError, ValueError) as exc:
        parser.exit(1, f"Sina probe failed ({type(exc).__name__})\n")


if __name__ == "__main__":
    main()
