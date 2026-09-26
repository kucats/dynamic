import cv2, numpy as np, json, sys
LET='CDEFGAB'
def staves_of(B):
    H,W=B.shape
    def lines_in(x0,x1,thr=0.7):
        rows=B[:,x0:x1].sum(1); n=x1-x0
        cand=[y for y in range(H) if rows[y]>thr*n]
        g=[]
        for y in cand:
            if g and y-g[-1][-1]<=2: g[-1].append(y)
            else: g.append([y])
        ys=[sum(q)/len(q) for q in g]; st=[]; i=0
        while i+4<len(ys):
            s=ys[i:i+5]; d=np.diff(s)
            if d.max()-d.min()<7 and 18<d.mean()<34: st.append(s); i+=5
            else: i+=1
        return st
    bands=[(x0,lines_in(x0,x0+300)) for x0 in (1400,500,2300,900,1900)]
    allst=sorted(((x0,s) for x0,band in bands for s in band),key=lambda t:t[1][0])
    merged=[]
    for x0,s in allst:
        if merged and abs(s[0]-merged[-1][0][1][0])<40: merged[-1].append((x0,s))
        else: merged.append([(x0,s)])
    out=[]
    for grp in merged:
        grp.sort(key=lambda t:t[0])
        out.append(dict(xl=grp[0][0]+150,xr=grp[-1][0]+150,l=grp[0][1],r=grp[-1][1],m=grp[len(grp)//2][1]))
    return out
def staff_y(st,x,k):  # line k (0 top) at x
    t=(x-st['xl'])/(st['xr']-st['xl'])
    return st['l'][k]+(st['r'][k]-st['l'][k])*t
def pname(step):  # step 0 = E4 (treble bottom line)
    d=2+step; return LET[d%7]+str(4+d//7)

def run(p):
    im=cv2.imread(f'work/p{p}.png',0); B=(im<140)
    b=B.astype(np.uint8)
    ST=staves_of(B)
    # filled heads
    k=cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(15,13))
    op=cv2.morphologyEx(b,cv2.MORPH_OPEN,k)
    n,lab,st,cen=cv2.connectedComponentsWithStats(op)
    C=[]
    for i in range(1,n):
        x,y,w,h,a=st[i]
        if 780<a<1300 and 27<=w<=44 and 26<=h<=42:
            C.append(dict(x=float(cen[i][0]),y=float(cen[i][1]),kind='f'))
    # hollow heads: remove staff lines, close, fill holes
    nb=b.copy()
    for s in ST:
        for kk in range(5):
            for x in range(0,b.shape[1],1):
                pass
    # vectorised staff removal: erase rows near staff lines where vertical run is short
    vert=cv2.morphologyEx(b,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_RECT,(1,6)))
    mask=np.zeros_like(b)
    for s in ST:
        for kk in range(5):
            xs=np.arange(b.shape[1])
            ys=np.round(staff_y(s,xs,kk)).astype(int)
            for dy in (-3,-2,-1,0,1,2,3):
                yy=np.clip(ys+dy,0,b.shape[0]-1); mask[yy,xs]=1
    nb=np.where(mask==1, vert|0, b).astype(np.uint8)
    nb=np.where(mask==1, np.maximum(vert, 0), b).astype(np.uint8)
    cl=cv2.morphologyEx(nb,cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))
    ff=(1-cl).copy(); m2=np.zeros((ff.shape[0]+2,ff.shape[1]+2),np.uint8)
    cv2.floodFill(ff,m2,(0,0),0)
    filled=cl|ff
    op2=cv2.morphologyEx(filled,cv2.MORPH_OPEN,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(17,13)))
    n2,lab2,st2,cen2=cv2.connectedComponentsWithStats(op2)
    for i in range(1,n2):
        x,y,w,h,a=st2[i]
        if 500<a<1500 and 26<=w<=50 and 20<=h<=42:
            cx,cy=cen2[i]
            if all(abs(cx-c['x'])>20 or abs(cy-c['y'])>20 for c in C):
                # hollow only if centre pixel is white
                if im[int(cy),int(cx)]>140 or b[int(cy)-3:int(cy)+4,int(cx)-3:int(cx)+4].mean()<0.5:
                    C.append(dict(x=float(cx),y=float(cy),kind='h'))
    # assign staff + pitch
    out=[]
    for c in C:
        best=None
        for si,s in enumerate(ST):
            top=staff_y(s,c['x'],0); bot=staff_y(s,c['x'],4)
            if top-110<c['y']<bot+110:
                d=abs(c['y']-(top+bot)/2)
                if best is None or d<best[0]: best=(d,si,top,bot)
        if not best: continue
        _,si,top,bot=best
        sp=(bot-top)/4; step=round((bot-c['y'])/(sp/2))
        out.append(dict(sys=si+1,x=round(c['x'],1),y=round(c['y'],1),kind=c['kind'],step=step,treble=pname(step)))
    out.sort(key=lambda d:(d['sys'],d['x']))
    for i,d in enumerate(out): d['cid']=i+1
    json.dump(dict(page=p,staves=[[round(v,1) for v in s['m']] for s in ST],cands=out),open(f'work/cand_p{p}.json','w'),indent=0)
    # overlay
    col=cv2.cvtColor(im,cv2.COLOR_GRAY2BGR)
    for d in out:
        clr=(0,0,255) if d['kind']=='f' else (255,0,200)
        cv2.circle(col,(int(d['x']),int(d['y'])),24,clr,3)
        cv2.putText(col,str(d['cid']),(int(d['x'])-18,int(d['y'])-30),cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,140,0),2)
        cv2.putText(col,d['treble'],(int(d['x'])-18,int(d['y'])+55),cv2.FONT_HERSHEY_SIMPLEX,0.7,(200,80,0),2)
    cv2.imwrite(f'work/ov_p{p}.png',col)
    print(p,len(ST),'staves',len(out),'cands',sum(d['kind']=='h' for d in out),'hollow')
if __name__=="__main__":
    for p in map(int,sys.argv[1:]): run(p)
