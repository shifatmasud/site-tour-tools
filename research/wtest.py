import subprocess,time,os
from playwright.sync_api import sync_playwright
x=subprocess.Popen(["Xvfb",":98","-screen","0","1440x900x24"],stderr=subprocess.DEVNULL);time.sleep(1)
env=dict(os.environ,DISPLAY=":98")
for args in [["--start-fullscreen"],["--kiosk","--start-fullscreen"],["--app=data:text/html,hi","--window-size=1440,900","--window-position=0,0"]]:
    with sync_playwright() as p:
        b=p.chromium.launch(headless=False,env=env,args=args+["--ignore-gpu-blocklist","--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"],ignore_default_args=["--enable-automation"])
        c=b.new_context(no_viewport=True); pg=c.new_page(); time.sleep(1.5)
        print(args, pg.evaluate("[innerWidth,innerHeight,screenX,screenY,outerWidth,outerHeight]"), flush=True)
        t=time.time()
        for i in range(30): pg.mouse.move(100+i,100)
        print(" move latency ms", round((time.time()-t)/30*1000,1), flush=True)
        b.close()
x.terminate()
