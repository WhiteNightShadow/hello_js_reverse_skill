# SPDX-License-Identifier: CC0-1.0
"""Own loopback server, adapted from the task-authored real-case harness.

The browser uses real CryptoJS; this server uses independent Python AES/HMAC.
Only allowlisted assets are served. No shared service metadata or process control.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import base64, hashlib, hmac, json, re, secrets, threading, time


def make_server(assets, work):
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad, unpad
    ROOT=Path(assets).resolve()
    RUNTIME=Path(work).resolve();RUNTIME.mkdir(exist_ok=True)
    KEYS=json.loads((ROOT/'crypto-fingerprint/samples/demo-keys.json').read_text(encoding='utf-8'))
    FIELDS=['v','alg','keyId','direction','requestId','method','path','ts','nonce','challengeId','fingerprint','iv','ciphertext']
    CONTEXT=['direction','requestId','method','path','nonce','challengeId','fingerprint']
    CHALLENGES={};NONCES={};LOCK=threading.Lock();TTL=120000;SKEW=30000

    def jsjson(value):
        text=json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False)
        return re.sub('[\ud800-\udfff]',lambda m:'\\u%04x'%ord(m[0]),text).encode('utf-8')

    def strict_json(raw):
        def pairs(items):
            out={}
            for key,value in items:
                if key in out:raise ValueError('duplicate JSON key')
                out[key]=value
            return out
        return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=lambda v:(_ for _ in ()).throw(ValueError('non-JSON number')))

    def verify(e):
        if not isinstance(e,dict) or set(e)!=set(FIELDS+['mac']):raise ValueError('INVALID_ENVELOPE')
        if e['v']!=1 or e['alg']!='AES-256-CBC+HMAC-SHA256' or e['keyId']!='demo-public-v1' or e['direction']!='request' or e['method']!='POST' or e['path']!='/local-sim/echo':raise ValueError('INVALID_ENVELOPE')
        for k in ['requestId','nonce','challengeId','iv']:
            if not isinstance(e[k],str) or re.fullmatch('[0-9a-f]{32}',e[k]) is None:raise ValueError('INVALID_ENVELOPE')
        for k in ['fingerprint','mac']:
            if not isinstance(e[k],str) or re.fullmatch('[0-9a-f]{64}',e[k]) is None:raise ValueError('INVALID_ENVELOPE')
        if type(e['ts']) is not int or not 0<=e['ts']<=2**53-1:raise ValueError('INVALID_ENVELOPE')
        ciphertext=base64.b64decode(e['ciphertext'],validate=True)
        if not ciphertext or len(ciphertext)%16 or base64.b64encode(ciphertext).decode()!=e['ciphertext']:raise ValueError('INVALID_ENVELOPE')
        expected=hmac.new(bytes.fromhex(KEYS['request']['macHex']),jsjson([e[k] for k in FIELDS]),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected,e['mac']):raise ValueError('INVALID_ENVELOPE')
        plaintext=unpad(AES.new(bytes.fromhex(KEYS['request']['encHex']),AES.MODE_CBC,bytes.fromhex(e['iv'])).decrypt(ciphertext),16)
        return strict_json(plaintext)

    def respond_crypto(e,payload):
        out={k:e[k] for k in FIELDS if k not in ['iv','ciphertext']}
        out.update(direction='response',ts=int(time.time()*1000),iv=secrets.token_hex(16))
        cipher=AES.new(bytes.fromhex(KEYS['response']['encHex']),AES.MODE_CBC,bytes.fromhex(out['iv']))
        out['ciphertext']=base64.b64encode(cipher.encrypt(pad(jsjson(payload),16))).decode()
        out['mac']=hmac.new(bytes.fromhex(KEYS['response']['macHex']),jsjson([out[k] for k in FIELDS]),hashlib.sha256).hexdigest()
        return out

    def asset(path):
        if path.startswith('/vm-assets/'):
            name=path.rsplit('/',1)[-1]
            if path.count('/') != 2:return None
            if name not in ['baseline.bundle.js','vm.bundle.js','cff.bundle.js','cff-disabled.bundle.js','selftest.js']:return None
            return ROOT/'vm-cff/dist'/name
        if path.startswith('/crypto-assets/'):
            name=path.rsplit('/',1)[-1]
            if path.count('/') != 2:return None
            if name not in ['crypto-js-4.2.0.js','case-crypto.js','fingerprintjs-5.2.0.js','fingerprint-adapter.js']:return None
            return ROOT/'crypto-fingerprint/assets'/name
        return None

    def page(kind):
        if kind in ['vm','cff']:
            ns='RealCasesVM' if kind=='vm' else 'RealCasesCFF';file='vm.bundle.js' if kind=='vm' else 'cff.bundle.js'
            scripts=''.join(f'<script src="/vm-assets/{name}"></script>' for name in ['baseline.bundle.js','vm.bundle.js','cff.bundle.js','cff-disabled.bundle.js','selftest.js'])
            code=f'''window.runCase=function(input){{const state={{nonAscii:0,calls:0,last:null,events:[]}};const result={ns}.unicodeDigest(input.text,input.salt,state);return {{result,state}};}};
            document.querySelector('#run').onclick=()=>{{window.caseOutput=runCase({{text:'中文😀 é',salt:4294967295}});document.querySelector('#result').textContent=JSON.stringify(window.caseOutput);document.body.dataset.done='true';}};'''
        else:
            scripts=''.join(f'<script src="/crypto-assets/{name}"></script>' for name in ['crypto-js-4.2.0.js','case-crypto.js','fingerprintjs-5.2.0.js','fingerprint-adapter.js'])
            code='''window.collectFingerprint=async()=>{window.fingerprintOutput=await CaseFingerprint.collect();document.querySelector('#result').textContent=JSON.stringify(fingerprintOutput);document.body.dataset.done='true';return {fingerprint:fingerprintOutput.fingerprint,componentCount:Object.keys(fingerprintOutput.components).length};};
            window.runExchange=async(message)=>{
                const fp=window.fingerprintOutput||await CaseFingerprint.collect();
                const keys=await(await fetch('/demo-keys')).json();
                const ch=await(await fetch('/challenge',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({fingerprint:fp.fingerprint})})).json();
                const meta={direction:'request',requestId:ch.requestId,method:'POST',path:'/local-sim/echo',ts:Date.now(),nonce:CaseCrypto.randomHex(),challengeId:ch.id,fingerprint:fp.fingerprint};
                const challengeAnswer=CaseCrypto.sha256(JSON.stringify(['local-challenge-v1',ch.id,meta.nonce,fp.fingerprint]));
                const request=CaseCrypto.seal({message,challengeAnswer},meta,keys);
                const response=await(await fetch('/local-sim/echo',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(request)})).json();
                const plain=CaseCrypto.open(response,keys,CaseCrypto.context(request,'response'));
                window.exchangeOutput={request,response,plain};document.querySelector('#result').textContent=JSON.stringify(exchangeOutput);document.body.dataset.done='true';return plain;
            };
            document.querySelector('#run').onclick=async()=>{try{await collectFingerprint();}catch(e){window.caseError=String(e);document.querySelector('#result').textContent=String(e);}};
            document.querySelector('#exchange').onclick=async()=>{try{await runExchange('真实CryptoJS往返🔐');}catch(e){window.caseError=String(e);document.querySelector('#result').textContent=String(e);}};'''
        return ('<!doctype html><meta charset="utf-8"><title>Local upstream '+kind+'</title><h1>'+kind+'</h1><button id="run">执行案例</button><button id="noop">空白对照</button><button id="exchange">加密往返</button><pre id="result"></pre>'+scripts+'<script>'+code+'</script>').encode()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def send(self,status,value,content_type='application/json'):
            body=value if isinstance(value,bytes) else jsjson(value)
            self.send_response(status);self.send_header('Content-Type',content_type);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store')
            self.send_header('Content-Security-Policy',"default-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self' data:")
            self.end_headers();self.wfile.write(body)
            with LOCK:
                with (RUNTIME/'http.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps({'t':time.time(),'method':self.command,'path':self.path,'status':status,'body_sha256':hashlib.sha256(body).hexdigest()},ensure_ascii=True)+'\n')
        def do_GET(self):
            path=self.path.split('?')[0]
            if path=='/blank':return self.send(200,b'<!doctype html><button id="noop">empty control</button>','text/html; charset=utf-8')
            if path=='/health':return self.send(200,{'ok':True})
            if path in ['/vm','/cff','/fingerprint','/crypto']:return self.send(200,page(path[1:]),'text/html; charset=utf-8')
            if path=='/demo-keys':return self.send(200,KEYS)
            if path=='/contract':return self.send(200,{'schema':'local-challenge-v1','ttl_ms':TTL,'clock_skew_ms':SKEW,'challenge':'/challenge','exchange':'/local-sim/echo','public_demo_keys':'/demo-keys','note':'Local simulation, not commercial anti-bot reproduction'})
            file=asset(path)
            if file and file.is_file():return self.send(200,file.read_bytes(),'application/javascript; charset=utf-8')
            return self.send(404,{'error':'not found'})
        def do_POST(self):
            try:
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=1024*1024:return self.send(413,{'error':'request too large'})
                raw=self.rfile.read(size);e=strict_json(raw)
            except Exception:return self.send(400,{'error':'INVALID_JSON'})
            if self.path=='/challenge':
                fp=e.get('fingerprint') if isinstance(e,dict) else None
                if not isinstance(fp,str) or not re.fullmatch('[0-9a-f]{64}',fp):return self.send(400,{'error':'INVALID_FINGERPRINT'})
                now=int(time.time()*1000);ch={'schema':'local-challenge-v1','id':secrets.token_hex(16),'requestId':secrets.token_hex(16),'fingerprint':fp,'issuedAt':now,'expiresAt':now+TTL,'used':False}
                with LOCK:
                    for key in list(CHALLENGES):
                        if CHALLENGES[key]['expiresAt']+10000<now:CHALLENGES.pop(key)
                    CHALLENGES[ch['id']]=ch
                return self.send(200,ch)
            if self.path!='/local-sim/echo':return self.send(404,{'error':'not found'})
            try:payload=verify(e)
            except Exception:return self.send(403,{'error':'INVALID_ENVELOPE'})
            now=int(time.time()*1000);error=None
            with LOCK:
                for nonce in list(NONCES):
                    if NONCES[nonce]<=now:NONCES.pop(nonce)
                ch=CHALLENGES.get(e['challengeId'])
                if not ch or ch['requestId']!=e['requestId']:error='UNKNOWN_CHALLENGE'
                elif now>=ch['expiresAt']:error='CHALLENGE_EXPIRED'
                elif abs(now-e['ts'])>SKEW or not ch['issuedAt']<=e['ts']<ch['expiresAt']:error='STALE_TIMESTAMP'
                elif ch['used']:error='CHALLENGE_USED'
                elif NONCES.get(e['nonce'],0)>now:error='NONCE_REPLAY'
                elif ch['fingerprint']!=e['fingerprint']:error='FINGERPRINT_MISMATCH'
                elif not isinstance(payload,dict) or payload.get('challengeAnswer')!=hashlib.sha256(jsjson(['local-challenge-v1',ch['id'],e['nonce'],e['fingerprint']])).hexdigest():error='BAD_ANSWER'
                else:ch['used']=True;NONCES[e['nonce']]=now+120000
            if error:return self.send(403,{'error':error})
            result={'ok':True,'echo':payload.get('message'),'requestId':e['requestId'],'fingerprint':e['fingerprint'],'receipt':secrets.token_hex(8)}
            return self.send(200,respond_crypto(e,result))

    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    server.daemon_threads=True
    server.timeout=10
    return server
