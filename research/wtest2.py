import subprocess,time,os
from playwright.sync_api import sync_playwright
from PIL import Image
x=subprocess.Popen(["Xvfb",":98","-screen","0","1440x1000x24"],stderr=subprocess.DEVNULL);time.sleep(1)
env=dict(os.environ,DISPLAY=":98")
with sync_playwright() as p:
    b=p.chromium.launch(headless=False,env=env,args=["--app=data:text/html,<body style='margin:0;background:rgb(255,0,0)'></body>","--window-size=1441,988","--window-position=0,0","--force-device-scale-factor=1","--ignore-gpu-blocklist","--use-gl=angle","--use-angle=swiftshader","--enable-unsafe-swiftshader"],ignore_default_args=["--enable-automation"])
    c=b.new_context(no_viewport=True); pg=c.new_page(); pg.set_content("<body style='margin:0;background:rgb(255,0,0)'></body>"); time.sleep(1.5)
    print(pg.evaluate("[innerWidth,innerHeight,screenX,screenY,outerWidth,outerHeight]"), flush=True)
    subprocess.run(["ffmpeg","-y","-loglevel","error","-f","x11grab","-video_size","1440x1000","-i",":98.0","-frames:v","1","/tmp/rec/root.png"],env=env)
    print([pp.url for pp in c.pages])
    b.close()
x.terminate()
im=Image.open('/tmp/rec/root.png').convert('RGB'); w,h=im.size
px=im.load()
ys=[y for y in range(h) if px[700,y]==(255,0,0)]; xs=[xx for xx in range(w) if px[xx,500]==(255,0,0)]
print('red y',ys[0],ys[-1],'x',xs[0],xs[-1])
