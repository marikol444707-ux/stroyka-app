from pathlib import Path
import subprocess,os,time,urllib.request,sys
p=Path(__file__).parent;script=sys.argv[1];port=sys.argv[2]if len(sys.argv)>2 else'9370';env=os.environ.copy();env['XDG_CACHE_HOME']=str(p/'cache')
with (p/(script+'.chromium.log')).open('w')as log:
 chrome=subprocess.Popen(['chromium','--headless','--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-background-networking','--no-first-run','--user-data-dir='+str(p/('verified-'+script+'-profile')),'--remote-debugging-port='+port,'about:blank'],stdout=log,stderr=subprocess.STDOUT,env=env)
 try:
  for i in range(100):
   try:urllib.request.urlopen('http://127.0.0.1:'+port+'/json',timeout=1).close();break
   except OSError:time.sleep(.1)
  with (p/(script+'.log')).open('w')as dst:r=subprocess.run(['node',script],cwd=p,stdout=dst,stderr=subprocess.STDOUT,timeout=360)
  assert r.returncode==0,script+' failed'
  assert 'PASS' in (p/(script+'.log')).read_text();print('PASS '+script,flush=True)
 finally:
  if chrome.poll()is None:chrome.terminate()
  try:chrome.wait(timeout=10)
  except subprocess.TimeoutExpired:chrome.kill();chrome.wait()
