#!/usr/bin/env python3
"""Inspect only the dependencies required by the selected workflow."""
import argparse
import importlib.util
import json
import shutil
import sys


def inspect(mode):
    checks=[]
    def command(name, required):
        path=shutil.which(name)
        checks.append({'name':name,'kind':'command','installed':bool(path),'required':required,'path':path})
    def module(name, required):
        try: found=importlib.util.find_spec(name) is not None
        except (ValueError, ModuleNotFoundError): found=False
        checks.append({'name':name,'kind':'python_module','installed':found,'required':required})
    if mode in ('all','node','wasm'):
        command('node',True);command('npm',True)
    if mode in ('all','python'):
        module('requests',True);module('Crypto',False)
    if mode in ('all','browser'):
        for name in ('camoufox','playwright','mcp','camoufox_reverse_mcp'): module(name,True)
        module('esprima',False)
    return {'mode':mode,'python':sys.executable,'checks':checks,
            'ok':all(c['installed'] or not c['required'] for c in checks),
            'note':'Python modules are checked in this interpreter; Node template dependencies are installed per project. Browser binaries/capabilities require check_environment().'}


if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser()
    parser.add_argument('--mode',choices=['all','node','python','wasm','browser'],default='all')
    parser.add_argument('--json',action='store_true')
    args=parser.parse_args();result=inspect(args.mode)
    if args.json: print(json.dumps(result,ensure_ascii=False,indent=2))
    else:
        print('Dependency check:',args.mode,'| Python:',result['python'])
        for item in result['checks']:
            print(('OK' if item['installed'] else 'MISSING')+' '+item['name']+' ('+('required' if item['required'] else 'optional')+')')
        print(result['note'])
    raise SystemExit(0 if result['ok'] else 1)
