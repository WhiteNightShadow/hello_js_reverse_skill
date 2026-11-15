import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'templates/python-request'))
import collect


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query=parse_qs(urlsplit(self.path).query)
        mode=query.get('mode',['page'])[0]
        if mode=='page':index=int(query.get('page',['1'])[0])-1
        elif mode=='offset':index=int(query.get('offset',['0'])[0])//2
        else:index=int(query.get('cursor',['0'])[0])
        items=[{'id':index+1}] if index<3 else []
        payload={'code':0,'data':{'items':items,'next':index+1 if index<2 else None}}
        raw=json.dumps(payload).encode()
        self.send_response(200);self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def log_message(self,*args):pass


class ScriptTests(unittest.TestCase):
    def test_baseline_create_check_change_missing_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'sdk.js';source.write_text('v1')
            command=[sys.executable,str(ROOT/'scripts/project-baseline.py')]
            def run(*args):return subprocess.run(command+list(args)+['--root',folder],capture_output=True,text=True)
            self.assertEqual(run('create','--files','sdk.js').returncode,0)
            self.assertEqual(run('check').returncode,0)
            self.assertNotEqual(run('create','--files','sdk.js').returncode,0)
            source.write_text('v2')
            result=run('check');self.assertEqual(result.returncode,1)
            self.assertEqual(json.loads(result.stdout)['changed'],['sdk.js'])
            source.unlink();self.assertEqual(json.loads(run('check').stdout)['missing'],['sdk.js'])

    def test_dependency_mode_does_not_require_other_language(self):
        spec=importlib.util.spec_from_file_location('deps',ROOT/'scripts/check-deps.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with patch.object(module.shutil,'which',return_value=None):
            result=module.inspect('python')
            self.assertNotIn('node',[item['name'] for item in result['checks']])
            self.assertTrue(result['ok'])
            self.assertFalse(module.inspect('node')['ok'])

    def test_real_loopback_page_offset_and_cursor_collection(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as folder:
                for mode in ('page','offset','cursor'):
                    with self.subTest(mode=mode):
                        config={'url':f'http://127.0.0.1:{server.server_port}/items',
                                'params':{'mode':mode},'items_path':'data.items',
                                'success_path':'code','success_value':0,'item_key':'id',
                                'pagination':{'mode':mode,'step':2 if mode=='offset' else 1,'next_path':'data.next'}}
                        output=Path(folder)/(mode+'.jsonl')
                        result=collect.run(config,output)
                        self.assertEqual(result['status'],'complete')
                        self.assertEqual([json.loads(line)['id'] for line in output.read_text().splitlines()],[1,2,3])
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)

    def test_legacy_node_test_entrypoints_stay_offline(self):
        for name in ('node-request','vm-sandbox','wasm-loader','browser-auto','env-bundle'):
            result=subprocess.run(['node',str(ROOT/'templates'/name/'main.js'),'--test'],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)


if __name__=='__main__':unittest.main()
