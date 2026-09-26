"""Guides: treble names (red/green), (bass) in grey, [alto] in purple.
Usage: python3 work/zoom.py PAGE SYS [X0 X1] [OUT]
Writes a zoomed crop of one system of page PAGE (300dpi image work/pPAGE.png) with:
 - left margin pitch guides: treble-clef names (red/green) and bass-clef names (grey, in brackets)
 - candidate noteheads from work/cand_pPAGE.json circled with their cid
 - an x-axis ruler in page pixel coordinates every 100px (use these x values in your output)
Default X range: whole width in two halves -> writes OUT_a.png and OUT_b.png
"""
import cv2, json, sys, numpy as np
import os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from cand import staves_of, staff_y
LET='CDEFGAB'
p=int(sys.argv[1]); s=int(sys.argv[2])
im=cv2.imread(f'work/p{p}.png',0); B=im<140
ovf=f'work/systems_p{p}.json'
if os.path.exists(ovf):
    # reviewed layout override: fit each line's left/right y to the image so skew is preserved
    def _fit(sys5):
        L=[];R=[]
        for k in range(5):
            y0=max(0,int(sys5[k])-9)
            for xw,out in ((range(300,900),L),(range(Wx-900,Wx-300),R)):
                band=B[y0:y0+19,xw.start:xw.stop]
                out.append(y0+int(band.sum(1).argmax()))
        return dict(xl=600,xr=Wx-600,l=L,r=R,m=sys5)
    Wx=B.shape[1]; ST=[_fit(s) for s in json.load(open(ovf))['systems']]
else:
    ST=staves_of(B)
st=ST[s-1]
cj=json.load(open(f'work/cand_p{p}.json'))
def render(x0,x1,out):
    top=int(min(st['l'][0],st['r'][0]))-170; bot=int(max(st['l'][4],st['r'][4]))+150
    top=max(0,top); bot=min(im.shape[0],bot)
    c=cv2.cvtColor(im[top:bot,x0:x1],cv2.COLOR_GRAY2BGR)
    pad=215
    c=cv2.copyMakeBorder(c,40,0,pad,0,cv2.BORDER_CONSTANT,value=(255,255,255))
    xm=(x0+x1)/2
    bl=staff_y(st,xm,4); sp=(staff_y(st,xm,4)-staff_y(st,xm,0))/4
    for k in range(-8,17):
        y=int(bl-k*sp/2-top)+40
        d=2+k; tn=LET[d%7]+str(4+d//7)
        db=4+k; bn=LET[db%7]+str(2+db//7)
        colr=(0,0,230) if k%2==0 else (0,150,0)
        cv2.putText(c,tn,(2,y+5),cv2.FONT_HERSHEY_SIMPLEX,0.45,colr,1)
        cv2.putText(c,'('+bn+')',(52,y+5),cv2.FONT_HERSHEY_SIMPLEX,0.4,(120,120,120),1)
        da=3+k; an=LET[da%7]+str(3+da//7)          # alto clef (C clef on the middle line)
        cv2.putText(c,'['+an+']',(112,y+5),cv2.FONT_HERSHEY_SIMPLEX,0.4,(170,0,170),1)
        cv2.line(c,(170,y),(pad-2,y),colr,1)
    for x in range((x0//100+1)*100,x1,100):
        X=x-x0+pad; cv2.line(c,(X,0),(X,14),(200,0,0),1)
        cv2.putText(c,str(x),(X-18,32),cv2.FONT_HERSHEY_SIMPLEX,0.45,(200,0,0),1)
    for d in cj['cands']:
        if d['sys']!=s or not(x0<=d['x']<x1): continue
        X=int(d['x']-x0+pad); Y=int(d['y']-top+40)
        cv2.circle(c,(X,Y),22,(0,0,255) if d['kind']=='f' else (255,0,200),2)
        cv2.putText(c,str(d['cid']),(X-14,Y-26),cv2.FONT_HERSHEY_SIMPLEX,0.55,(0,130,0),2)
    c=cv2.resize(c,None,fx=1.3,fy=1.3)
    cv2.imwrite(out,c)
    print('wrote',out,'page-y range',top,bot)
if len(sys.argv)>=5:
    render(int(sys.argv[3]),int(sys.argv[4]),sys.argv[5] if len(sys.argv)>5 else f'work/z_p{p}_s{s}.png')
else:
    o=sys.argv[3] if len(sys.argv)>3 else f'work/z_p{p}_s{s}'
    W=im.shape[1]; render(0,W//2+120,o+'_a.png'); render(W//2-120,W,o+'_b.png')
