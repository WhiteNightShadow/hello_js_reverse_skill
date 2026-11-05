#!/usr/bin/env python3
"""Keep an auditable ledger of online attempts and verify single-variable claims.

record   append one attempt with an explicit outcome class
gate     decide whether another online attempt is allowed
summary  count attempts without merging different outcome classes
audit    compare two saved requests and report only hashes and lengths
"""
import argparse
import fnmatch
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

OUTCOMES = ('not_sent', 'transport_error', 'rejected', 'accepted', 'target_ok')
EXIT_BLOCKED = 2


def read_ledger(path):
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    with path.open(encoding='utf-8') as stream:
        for line in stream:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def record(args):
    entry = {'ts': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'batch': args.batch,
             'variant': args.variant, 'outcome': args.outcome, 'attempts': args.attempts}
    if args.evidence:
        entry['evidence'] = args.evidence
    if args.note:
        entry['note'] = args.note
    ledger = Path(args.ledger)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps(entry, ensure_ascii=False) + '\n')
    print(json.dumps({'status': 'recorded', **entry}, ensure_ascii=False))
    return 0


def parse_instant(value):
    try:
        return float(value)
    except ValueError:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('--expires-at needs a timezone or unix seconds')
        return parsed.timestamp()


def gate(args):
    rows = [row for row in read_ledger(args.ledger) if row.get('batch') == args.batch]
    sent = [row for row in rows if row.get('outcome') != 'not_sent']
    reasons = []
    if not args.allow_rejections and any(row.get('outcome') == 'rejected' for row in rows):
        reasons.append('rejected_in_batch')
    if any(row.get('attempts') == 'unknown' for row in sent):
        reasons.append('attempts_unknown')
    if len(sent) >= args.budget:
        reasons.append('budget_exhausted')
    if bool(args.sdk_local) != bool(args.sdk_page):
        raise SystemExit('--sdk-local and --sdk-page must be given together')
    if args.sdk_local and args.sdk_local != args.sdk_page:
        reasons.append('sdk_mismatch')
    remaining = None
    if args.expires_at:
        remaining = parse_instant(args.expires_at) - time.time()
        if remaining < args.min_remaining:
            reasons.append('credential_expiring')
    result = {'allowed': not reasons, 'reasons': reasons, 'batch': args.batch, 'sent': len(sent),
              'budget': args.budget, 'credential_remaining_seconds': None if remaining is None else int(remaining)}
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['allowed'] else EXIT_BLOCKED


def summary(args):
    batches = {}
    for row in read_ledger(args.ledger):
        batch = batches.setdefault(row.get('batch'), {name: 0 for name in OUTCOMES})
        batch[row.get('outcome')] = batch.get(row.get('outcome'), 0) + 1
        batch['attempts_unknown'] = batch.get('attempts_unknown', False) or row.get('attempts') == 'unknown'
    print(json.dumps(batches, ensure_ascii=False, indent=2))
    return 0


def load_request(path):
    data = json.loads(Path(path).read_text(encoding='utf-8'))
    headers = data.get('headers', [])
    pairs = list(headers.items()) if isinstance(headers, dict) else [tuple(item) for item in headers]
    return {'method': str(data.get('method', 'GET')).upper(), 'url': str(data.get('url', '')),
            'headers': [(str(name), str(value)) for name, value in pairs], 'body': data.get('body')}


def flatten(request):
    """Map a request to named fields so differences can be reported one by one."""
    fields = {'method': request['method']}
    url = urlsplit(request['url'])
    fields['url.base'] = f'{url.scheme}://{url.netloc}{url.path}'
    query = parse_qsl(url.query, keep_blank_values=True)
    fields['query.order'] = json.dumps([name for name, _ in query])
    for name in dict(query):
        fields[f'query:{name}'] = json.dumps([value for key, value in query if key == name])
    names = []
    for name, value in request['headers']:
        lowered = name.lower()
        names.append(lowered)
        if lowered == 'cookie':
            pairs = [part.strip().split('=', 1) for part in value.split(';') if part.strip()]
            fields['cookie.order'] = json.dumps([pair[0] for pair in pairs])
            for pair in pairs:
                fields[f'cookie:{pair[0]}'] = pair[1] if len(pair) == 2 else ''
        else:
            key = f'header:{lowered}'
            fields[key] = value if key not in fields else fields[key] + '\n' + value
    fields['header.order'] = json.dumps(names)
    if request['body'] is not None:
        body = request['body']
        fields['body'] = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False, sort_keys=True)
    return fields


def mask(value):
    if value is None:
        return None
    raw = value.encode('utf-8', 'surrogatepass')
    return {'sha256': hashlib.sha256(raw).hexdigest()[:16], 'length': len(raw)}


def matches(field, patterns):
    short = field.split(':', 1)[1] if ':' in field else field
    return any(fnmatch.fnmatchcase(field.lower(), item.lower()) or fnmatch.fnmatchcase(short.lower(), item.lower())
               for item in patterns)


def audit(args):
    base, candidate = flatten(load_request(args.base)), flatten(load_request(args.candidate))
    changed = sorted(key for key in base.keys() | candidate.keys() if base.get(key) != candidate.get(key))
    rows = [{'field': key, 'base': mask(base.get(key)), 'candidate': mask(candidate.get(key))} for key in changed]
    unexpected = [key for key in changed if not matches(key, args.allow + args.must_change)]
    missing = [item for item in args.must_change if not any(matches(key, [item]) for key in changed)]
    result = {'single_variable_confirmed': not unexpected and not missing, 'changed': rows,
              'unexpected': unexpected, 'missing_change': missing,
              'order_changed': any(key.endswith('.order') for key in changed)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['single_variable_confirmed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    item = commands.add_parser('record')
    item.add_argument('--ledger', required=True)
    item.add_argument('--batch', required=True)
    item.add_argument('--variant', required=True)
    item.add_argument('--outcome', required=True, choices=OUTCOMES)
    item.add_argument('--attempts', default=1, type=lambda v: v if v == 'unknown' else int(v),
                      help='real attempt count; use "unknown" when a helper may have retried')
    item.add_argument('--evidence')
    item.add_argument('--note')
    item.set_defaults(run=record)
    item = commands.add_parser('gate')
    item.add_argument('--ledger', required=True)
    item.add_argument('--batch', required=True)
    item.add_argument('--budget', required=True, type=int)
    item.add_argument('--allow-rejections', action='store_true',
                      help='pre-declared stability batch: rejections are measurements, only the budget stops it')
    item.add_argument('--sdk-local', help='hash of the local SDK copy')
    item.add_argument('--sdk-page', help='hash of the SDK the page loads now')
    item.add_argument('--expires-at', help='credential expiry: unix seconds or ISO-8601 with timezone')
    item.add_argument('--min-remaining', default=60, type=int, help='seconds of credential life this batch needs')
    item.set_defaults(run=gate)
    item = commands.add_parser('summary')
    item.add_argument('--ledger', required=True)
    item.set_defaults(run=summary)
    item = commands.add_parser('audit')
    item.add_argument('--base', required=True, help='JSON file with method, url, headers and body')
    item.add_argument('--candidate', required=True)
    item.add_argument('--allow', action='append', default=[], help='field or name that may differ; globs allowed')
    item.add_argument('--must-change', action='append', default=[], help='field or name that has to differ')
    item.set_defaults(run=audit)
    args = parser.parse_args()
    return args.run(args)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
