import json,sys
from fractions import Fraction as F
p=int(sys.argv[1]); d=json.load(open(f'work/final_p{p}.json'))
m=d.get('meta',{}); mets=sorted(m.get('meters',[]),key=lambda x:x['bar'])
def meter(bar, default=None):
    cur=default
    for e in mets:
        if e['bar']<=bar: cur=e['meter']
    return cur
bad=0; missing=0
by={}
for i,n in enumerate(d['notes']):
    if 'dur' not in n or 'off' not in n or n.get('bar') is None: missing+=1; continue
    by.setdefault(n['bar'],[]).append((F(n['off']),F(n['dur']),i+1,n['pitch']))
for b,ns in sorted(by.items()):
    mt=meter(b)
    L=F(mt) if mt else None
    ns.sort()
    for k,(o,du,i,pp) in enumerate(ns):
        if L is not None and o+du>L: print(f'bar {b}: note #{i} {pp} off {o} dur {du} exceeds bar length {L} ({mt})'); bad+=1
        if k+1<len(ns) and ns[k+1][0] < o+du and du>0: print(f'bar {b}: note #{i} overlaps next note #{ns[k+1][2]}'); bad+=1
print('missing fields:',missing,' problems:',bad, ' (meter unknown for bars before first meter entry on this page -> pass "meters" including the meter in force at the top of the page)')
