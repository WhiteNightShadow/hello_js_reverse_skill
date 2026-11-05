#!/usr/bin/env python3
"""Inspect a batch of opaque tokens without assuming any site or SDK.

Reports text shape, decoded byte statistics, stable byte runs aligned from the
head and the tail, length-field candidates and optional per-token XOR masks.
Structure says nothing about whether a server accepts a token.
"""
import argparse
import base64
import json
import math
import sys
import zlib
from collections import Counter
from pathlib import Path

HEX = set('0123456789abcdefABCDEF')
STANDARD = set('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/')
URL_SAFE = (STANDARD - set('+/')) | set('-_')
CHECKSUMS = {'crc32': zlib.crc32, 'adler32': zlib.adler32}


def read_tokens(path, field):
    text = sys.stdin.read() if path == '-' else Path(path).read_text(encoding='utf-8')
    stripped = text.lstrip()
    if stripped.startswith('['):
        return [str(item) for item in json.loads(text)]
    tokens = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if field:
            value = json.loads(line)
            for key in field.split('.'):
                value = value[key]
            tokens.append(str(value))
        else:
            tokens.append(line.strip())
    return tokens


def text_shape(tokens):
    lengths = [len(token) for token in tokens]
    chars = set().union(*[set(token.rstrip('=')) for token in tokens])
    if chars <= HEX:
        guess = 'hex'
    elif chars <= STANDARD:
        guess = 'base64-or-custom-alphabet'
    elif chars <= URL_SAFE:
        guess = 'base64url'
    else:
        guess = 'other'
    return {'count': len(tokens), 'length_min': min(lengths), 'length_max': max(lengths),
            'distinct_lengths': len(set(lengths)), 'all_length_multiple_of_4': all(n % 4 == 0 for n in lengths),
            'has_padding': any(token.endswith('=') for token in tokens), 'distinct_chars': len(chars), 'guess': guess}


def decode_custom(token, alphabet):
    table = {char: index for index, char in enumerate(alphabet)}
    bits = count = 0
    output = bytearray()
    for char in token.rstrip('='):
        bits = (bits << 6) | table[char]
        count += 6
        if count >= 8:
            count -= 8
            output.append((bits >> count) & 0xFF)
    return bytes(output)


def decode(token, encoding, alphabet):
    if encoding == 'hex':
        return bytes.fromhex(token)
    if encoding == 'raw':
        return token.encode('utf-8')
    if encoding == 'custom':
        return decode_custom(token, alphabet)
    padded = token.rstrip('=') + '=' * (-len(token.rstrip('=')) % 4)
    return base64.urlsafe_b64decode(padded) if encoding == 'base64url' else base64.b64decode(padded)


def xor_bytes(data, key):
    return bytes(value ^ key for value in data)


def anchor_score(rows, anchor):
    size = len(rows[0])
    return sum(1 for index in range(size) if len({row[index] ^ row[anchor] for row in rows}) == 1)


def align_xor(items, max_anchors=64):
    """Remove a per-token single-byte mask without knowing any key.

    XOR of two positions in one token cancels the mask, so positions that are
    stable in plaintext keep a constant XOR against a stable anchor in every
    token. The anchor with the most such positions wins, searched from the
    head and from the tail because variable fields can sit on either side.
    """
    size = min(len(item) for item in items)
    best = (0, None, None)
    for tail in (False, True):
        rows = [item[-size:] if tail else item[:size] for item in items]
        for anchor in range(min(max_anchors, size)):
            position = size - 1 - anchor if tail else anchor
            score = anchor_score(rows, position)
            if score > best[0]:
                best = (score, position, rows)
    score, anchor, rows = best
    if rows is None:
        return [0] * len(items), None, 0.0
    return [row[anchor] ^ rows[0][anchor] for row in rows], anchor, round(score / size, 4)


def find_reference_key(reference, magic, offset):
    size = len(magic)
    return [key for key in range(256) if xor_bytes(reference[offset:offset + size], key) == magic]


def checksum_key(reference, name, offset, size=4):
    keys = []
    for key in range(256):
        data = xor_bytes(reference, key)
        stored = data[offset:offset + size]
        for order in ('little', 'big'):
            if int.from_bytes(stored, order) == CHECKSUMS[name](data[offset + size:]) & 0xFFFFFFFF:
                keys.append({'key': key, 'endian': order})
    return keys


def stable_runs(items, tail=False, min_run=2):
    size = min(len(item) for item in items)
    rows = [item[-size:] if tail and size else item[:size] for item in items]
    runs, start = [], None
    for index in range(size + 1):
        stable = index < size and len({row[index] for row in rows}) == 1
        if stable and start is None:
            start = index
        elif not stable and start is not None:
            if index - start >= min_run:
                offset = start - size if tail else start
                runs.append({'offset': offset, 'length': index - start, 'hex': rows[0][start:index].hex()})
            start = None
    return runs


def entropy(data):
    if not data:
        return 0.0
    counts = Counter(data)
    return -sum(count / len(data) * math.log2(count / len(data)) for count in counts.values())


def length_fields(items, max_offset=32, max_delta=64):
    found = []
    limit = min(max_offset, min(len(item) for item in items) - 4)
    for offset in range(max(limit, 0)):
        for width in (2, 4):
            for order in ('little', 'big'):
                deltas = {len(item) - int.from_bytes(item[offset:offset + width], order) for item in items}
                if len(deltas) == 1 and 0 <= next(iter(deltas)) <= max_delta:
                    found.append({'offset': offset, 'width': width, 'endian': order, 'delta': next(iter(deltas))})
    return found


def analyze(tokens, args):
    report = {'text': text_shape(tokens)}
    if args.encoding == 'none':
        return report
    items = [decode(token, args.encoding, args.alphabet) for token in tokens]
    if args.xor_align and len(items) > 1:
        keys, anchor, stable_ratio = align_xor(items)
        reference_key = 0
        xor = {'relative_keys': keys, 'anchor': anchor, 'stable_position_ratio': stable_ratio}
        if args.magic:
            candidates = find_reference_key(items[0], bytes.fromhex(args.magic), args.magic_offset)
            xor['reference_key_candidates'] = candidates
            reference_key = candidates[0] if candidates else 0
        if args.checksum:
            matches = checksum_key(items[0], args.checksum, args.checksum_offset)
            xor['checksum_matches'] = matches
            if matches and not args.magic:
                reference_key = matches[0]['key']
        report['xor'] = xor
        items = [xor_bytes(item, key ^ reference_key) for item, key in zip(items, keys)]
    joined = b''.join(items)
    report['bytes'] = {'length_min': min(map(len, items)), 'length_max': max(map(len, items)),
                       'mean_entropy_bits': round(sum(map(entropy, items)) / len(items), 3),
                       'zero_byte_ratio': round(joined.count(0) / len(joined), 4) if joined else 0.0}
    if len(items) > 1:
        report['head_stable_runs'] = stable_runs(items, min_run=args.min_run)
        report['tail_stable_runs'] = stable_runs(items, tail=True, min_run=args.min_run)
        report['length_field_candidates'] = length_fields(items)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('samples', help='one token per line, a JSON array, or - for stdin')
    parser.add_argument('--field', help='dotted field when each line is a JSON object')
    parser.add_argument('--encoding', default='none', choices=['none', 'raw', 'hex', 'base64', 'base64url', 'custom'])
    parser.add_argument('--alphabet', help='64-character alphabet for --encoding custom')
    parser.add_argument('--xor-align', action='store_true', help='remove a per-token single-byte XOR mask')
    parser.add_argument('--magic', help='known bytes as hex, used to resolve the absolute XOR key')
    parser.add_argument('--magic-offset', default=0, type=int)
    parser.add_argument('--checksum', choices=sorted(CHECKSUMS), help='resolve the XOR key by self-checking')
    parser.add_argument('--checksum-offset', default=0, type=int)
    parser.add_argument('--min-run', default=2, type=int, help='shortest stable run to report')
    args = parser.parse_args()
    if args.encoding == 'custom' and (not args.alphabet or len(set(args.alphabet)) != 64):
        parser.error('--encoding custom needs --alphabet with 64 distinct characters')
    tokens = read_tokens(args.samples, args.field)
    if not tokens:
        parser.error('no tokens found')
    print(json.dumps(analyze(tokens, args), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
