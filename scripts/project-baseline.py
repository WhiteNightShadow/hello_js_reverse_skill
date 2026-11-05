#!/usr/bin/env python3
"""Create/check portable project baselines without storing source or credentials."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def snapshot(root, files):
    result={}
    for name in files:
        path=(root/name).resolve()
        if not path.is_relative_to(root):
            raise ValueError('baseline files must stay inside the project root')
        key=path.relative_to(root).as_posix()
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(65536),b''):digest.update(chunk)
        result[key]=digest.hexdigest()
    return result


def current_skill_version():
    text=(Path(__file__).resolve().parents[1]/'SKILL.md').read_text(encoding='utf-8')
    match=re.search(r'^\s*version:\s*"([^"]+)"',text,re.M)
    return match.group(1) if match else 'unknown'


def parse_identities(items):
    result={}
    for item in items:
        name,separator,value=item.partition('=')
        if not separator or not name or not value:raise ValueError('--identity expects name=value')
        result[name]=value
    return result


def main():
    parser=argparse.ArgumentParser(description='Record SDK/signer/fixture hashes for upgrade reviews')
    parser.add_argument('action',choices=['create','check'])
    parser.add_argument('--root',default='.')
    parser.add_argument('--manifest',default='project-manifest.json')
    parser.add_argument('--files',nargs='+')
    parser.add_argument('--skill-version',default=current_skill_version())
    parser.add_argument('--mcp-version',default='unknown')
    parser.add_argument('--browser-version',default='unknown')
    parser.add_argument('--identity',action='append',default=[],help='name=value, for example sdk_public=1.2.3 or impl_revision=v2; identities cannot be derived from each other')
    args=parser.parse_args();root=Path(args.root).resolve();manifest=(root/args.manifest).resolve()
    if not manifest.is_relative_to(root):raise ValueError('manifest must stay inside project root')
    if args.action=='create':
        if not args.files:parser.error('create requires --files')
        data={'schema_version':1,'versions':{'skill':args.skill_version,'mcp':args.mcp_version,'browser':args.browser_version},'files':snapshot(root,args.files)}
        identities=parse_identities(args.identity)
        if identities:data['identities']=identities
        if manifest.relative_to(root).as_posix() in data['files']:raise ValueError('manifest cannot hash itself')
        manifest.parent.mkdir(parents=True,exist_ok=True)
        with manifest.open('x',encoding='utf-8') as stream:json.dump(data,stream,ensure_ascii=False,indent=2)
        print(json.dumps({'status':'created','manifest':str(manifest),'files':len(data['files'])}));return 0
    data=json.loads(manifest.read_text(encoding='utf-8'))
    if data.get('schema_version')!=1:raise ValueError('unsupported baseline schema')
    changed=[];missing=[]
    for name,expected in data['files'].items():
        try:
            if snapshot(root,[name])[name]!=expected:changed.append(name)
        except FileNotFoundError:missing.append(name)
    print(json.dumps({'status':'changed' if changed or missing else 'unchanged','changed':changed,'missing':missing,'versions':data.get('versions',{}),'identities':data.get('identities',{})},ensure_ascii=False))
    return 1 if changed or missing else 0


if __name__=='__main__':raise SystemExit(main())
