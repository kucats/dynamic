import cv2, json, sys
p=int(sys.argv[1]); d=json.load(open(f'work/final_p{p}.json'))
im=cv2.cvtColor(cv2.imread(f'work/p{p}.png',0),cv2.COLOR_GRAY2BGR)
for i,n in enumerate(d['notes'],1):
    x,y=int(n['x']),int(n['y']); c=(0,0,255) if n.get('clef','G')=='G' else (200,0,200)
    cv2.circle(im,(x,y),22,c,2)
    cv2.putText(im,n['pitch'],(x-22,y+52),cv2.FONT_HERSHEY_SIMPLEX,0.7,(200,60,0),2)
    cv2.putText(im,str(i),(x-12,y-28),cv2.FONT_HERSHEY_SIMPLEX,0.5,(0,130,0),1)
H=im.shape[0]; k=0
for y0 in range(0,H,1000):
    k+=1; cv2.imwrite(f'work/chk_p{p}_{k}.png',cv2.resize(im[y0:y0+1050],None,fx=0.7,fy=0.7))
print('notes',len(d['notes']),'images',k)
