import numpy as np
def barlines(B, s, note_xs):
    """B: bool image (dark), s: 5 staff line ys (avg), returns sorted x of barlines, staff x-extent."""
    top=int(round(s[0])); bot=int(round(s[4]))
    H,W=B.shape
    band=B[top-1:bot+2,:]
    full=band.mean(0)>0.93                      # column dark along the whole staff height
    above=B[max(0,top-14):top-5,:].mean(0)       # extends above?
    below=B[bot+5:bot+14,:].mean(0)
    cand=[x for x in range(W) if full[x] and above[x]<0.5 and below[x]<0.5]
    # group adjacent columns
    groups=[]
    for x in cand:
        if groups and x-groups[-1][-1]<=2: groups[-1].append(x)
        else: groups.append([x])
    xs=[]
    for g in groups:
        w=len(g); cx=sum(g)/w
        if w>9: continue                          # thick block (rest / beam)
        if any(abs(cx-nx)<24 for nx in note_xs): continue   # stem of a note
        xs.append(cx)
    # staff extent
    row=B[int(round(s[2])),:]
    cols=np.where(B[int(round(s[0])),:] & B[int(round(s[4])),:])[0]
    x0=int(cols.min()) if len(cols) else 0; x1=int(cols.max()) if len(cols) else W
    # merge double barlines / repeat signs (within 30px)
    m=[]
    for x in xs:
        if m and x-m[-1]<30: m[-1]=x
        else: m.append(x)
    m=[x for x in m if x-x0>40]    # drop the system's opening line
    return m,x0,x1

def is_multirest(B, s, xa, xb):
    """thick horizontal bar across the middle (multi-bar rest) or tall thick block between lines 2-4"""
    xa=int(xa)+4; xb=int(xb)-4
    if xb-xa<20: return False
    y1=int(round(s[1])); y3=int(round(s[3]))
    band=B[y1:y3+1, xa:xb]
    # columns with a long dark vertical run inside the band (excluding thin lines)
    colsum=band.sum(0)
    thick=colsum>=0.55*(y3-y1+1)
    # horizontal bar: many consecutive thick-ish rows of dark in middle area
    mid=B[int(round(s[1]))+4:int(round(s[3]))-3, xa:xb]
    rowfull=(mid.mean(1))
    run=0;best=0
    for x in range(mid.shape[1]):
        if mid[:,x].mean()>0.45: run+=1; best=max(best,run)
        else: run=0
    if best>=70: return True
    # tall block
    run=0;b2=0
    for x in range(len(thick)):
        if thick[x]: run+=1; b2=max(b2,run)
        else: run=0
    return 10<=b2<=45

def assign_bars(segs, first_bar, last_bar):
    """segs: list of dict(nb=[bar numbers of notes inside], multi=bool). returns list of labels (str or '')."""
    n=len(segs); lab=['']*n
    anch={}
    for i,sg in enumerate(segs):
        if sg['nb']:
            from collections import Counter
            anch[i]=Counter(sg['nb']).most_common(1)[0][0]
    if n: anch.setdefault(0,first_bar); anch.setdefault(n-1,last_bar)
    keys=sorted(anch)
    # drop anchors that are not increasing
    clean=[]
    for k in keys:
        if clean and anch[k]<=anch[clean[-1]]: continue
        clean.append(k)
    for k in clean: lab[k]=str(anch[k])
    for a,b in zip(clean,clean[1:]):
        ba,bb=anch[a],anch[b]; U=list(range(a+1,b)); M=bb-ba-1
        if not U: continue
        if M==len(U):
            for t,i in enumerate(U): lab[i]=str(ba+1+t)
            continue
        if M<len(U): continue
        mr=[i for i in U if segs[i]['multi']]
        if not mr: continue
        # from left until first multirest
        cur=ba
        for i in U:
            if segs[i]['multi']: break
            cur+=1; lab[i]=str(cur)
        cur2=bb
        for i in reversed(U):
            if segs[i]['multi']: break
            cur2-=1; lab[i]=str(cur2)
        if len(mr)==1:
            i=mr[0]; lo=cur+1; hi=cur2-1
            lab[i]=f'{lo}–{hi}' if hi>lo else str(lo)
        elif mr:
            # several multirests: label them only when we cannot know -> blank
            pass
    return lab
