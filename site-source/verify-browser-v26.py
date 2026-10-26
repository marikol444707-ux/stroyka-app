from pathlib import Path
import subprocess,os,time,urllib.request,sys
p=Path(__file__).parent;env=os.environ.copy();env['XDG_CACHE_HOME']=str(p/'cache')
cases=[('capture-realism.cjs',9369,'realism-capture.log'),('check-realism-browser.cjs',9368,'realism-browser-check.log'),('check-rooms-browser.cjs',9351,'rooms-browser-check.log'),('check-materials.cjs',9351,'materials-check.log'),('check-family-plan-browser.cjs',9366,'family-plan-browser-check.log')]
for script,port,log in cases:
 if len(sys.argv)>1 and script not in sys.argv[1:]:continue
 with (p/(script+'.chromium.log')).open('w') as dst:
  chrome=subprocess.Popen(['chromium','--headless','--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--use-angle=swiftshader','--enable-unsafe-swiftshader','--disable-background-networking','--no-first-run','--user-data-dir='+str(p/('verified-profile-'+str(port))),'--remote-debugging-port='+str(port),'about:blank'],stdout=dst,stderr=subprocess.STDOUT,env=env)
  try:
   for _ in range(100):
    try:urllib.request.urlopen('http://127.0.0.1:'+str(port)+'/json',timeout=1).close();break
    except OSError:time.sleep(.1)
   with (p/log).open('w') as output:r=subprocess.run(['node',script],cwd=p,stdout=output,stderr=subprocess.STDOUT,timeout=360)
   assert r.returncode==0,script+' failed: '+log
   assert 'PASS' in (p/log).read_text();print('PASS '+script,flush=True)
  finally:
   if chrome.poll() is None:chrome.terminate()
   try:chrome.wait(timeout=10)
   except subprocess.TimeoutExpired:chrome.kill();chrome.wait()
