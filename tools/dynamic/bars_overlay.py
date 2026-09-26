import cv2,json,sys
p=int(sys.argv[1]); src=sys.argv[2] if len(sys.argv)>2 else f'work/bars_auto_p{p}.json'
d=json.load(open(src)); im=cv2.cvtColor(cv2.imread(f'work/p{p}.png',0),cv2.COLOR_GRAY2BGR)
import os,sys as _s; _s.path.insert(0,os.path.dirname(__file__)); from common import staves, staves_override
ST=staves_override(p) or staves(cv2.imread(f'work/p{p}.png',0)<140)
for k,segs in d.items():
    s=ST[int(k)-1]
    for i,g in enumerate(segs):
        cv2.line(im,(int(g['xa']),int(s[0])-30),(int(g['xa']),int(s[4])+30),(0,0,255),2)
        cv2.putText(im,f"{k}.{i}:{g['label'] or '?'}",(int(g['xa'])+4,int(s[4])+58),cv2.FONT_HERSHEY_SIMPLEX,0.75,(0,90,200),2)
H=im.shape[0];n=0
for y0 in range(0,H,1000):
    n+=1; cv2.imwrite(f'work/barsov_p{p}_{n}.png',cv2.resize(im[y0:y0+1050],None,fx=0.7,fy=0.7))
print('wrote',n,'images')
