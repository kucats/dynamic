"""Render review strips and a PDF from source-coordinate pitch records."""
import argparse,json,re
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

def pitch_parts(label):
    match=re.fullmatch(r'(.+?)(-?\d+)',label)
    return (match.group(1),match.group(2)) if match else (label,'')

def render(data,images,out,font_path):
    doc=json.loads(data.read_text());notes={n['id']:n for n in doc['notes']};out.mkdir(parents=True,exist_ok=True)
    pdf=canvas.Canvas(str(out/'dvorak8-trombone2-pitch-reading-with-positions.pdf'))
    pdf.setTitle('Dvorak 8 - Trombone II - concert pitch reading')
    font=ImageFont.truetype(str(font_path),19)
    small=ImageFont.truetype(str(font_path),15)
    octave_font=ImageFont.truetype(str(font_path),9)
    for page in doc['pages']:
        pn=page['page'];im=Image.open(images/f'page-{pn:02d}.jpg').convert('RGB');w,h=im.size
        strips=[]
        for i,sys in enumerate(page['systems']):
            top=int(sys['top']*h);bottom=int(sys['bottom']*h)
            y0=int((page['systems'][i-1]['bottom']*h+top)/2) if i else max(0,top-80)
            y1=int((bottom+page['systems'][i+1]['top']*h)/2) if i+1<len(page['systems']) else bottom+50
            ns=sorted([notes[x] for x in sys['notes'] if notes[x]['role']=='play'],key=lambda n:n['x'])
            lanes=[];ends=[0,0,0]
            for n in ns:
                label=n['german_pitch'];x=n['x']*w
                pitch,octave=pitch_parts(label)
                alternates=','.join(str(p) for p in n['slide_positions'][1:])
                position=f"{n['recommended_slide_position']}"+(f" (alt {alternates})" if alternates else '')
                pitch_width=font.getlength(pitch)+octave_font.getlength(octave)+(2 if octave else 0)
                length=max(pitch_width,small.getlength(position))
                lane=next((j for j,e in enumerate(ends) if x-length/2>e+3),2)
                ends[lane]=x+length/2;lanes.append((n,lane))
            strip=Image.new('RGB',(w,y1-y0+112),'white');strip.paste(im.crop((0,y0,w,y1)),(0,0));d=ImageDraw.Draw(strip)
            d.line((120,y1-y0,w-100,y1-y0),fill='#d9e4ea',width=1)
            d.text((12,y1-y0+6),f'p{pn} / s{sys["system"]}',font=small,fill='#516779')
            for n,lane in lanes:
                x=n['x']*w;y=n['y']*h-y0;ly=y1-y0+3+lane*32
                pitch,octave=pitch_parts(n['german_pitch'])
                alternates=','.join(str(p) for p in n['slide_positions'][1:])
                position=f"{n['recommended_slide_position']}"+(f" (alt {alternates})" if alternates else '')
                color='#075d82' if n['status']=='visually_checked' else '#a55710'
                d.ellipse((x-9,y-8,x+9,y+8),outline=color,width=1)
                d.line((x,y+12,x,ly),fill='#c6cdd1',width=1)
                pitch_width=font.getlength(pitch)
                octave_width=octave_font.getlength(octave)
                text_width=pitch_width+octave_width+(2 if octave else 0)
                text_x=x-text_width/2
                d.text((text_x,ly),pitch,anchor='lt',font=font,fill=color)
                if octave:
                    d.text((text_x+pitch_width+2,ly-1),octave,anchor='lt',font=octave_font,fill='#aeb7bc')
                d.text((x,ly+20),position,anchor='mt',font=small,fill=color)
            strip.save(out/f'qa-p{pn:02d}-s{sys["system"]:02d}.png');strips.append(strip)
        pw=850;scale=pw/w;ph=sum(s.height for s in strips)*scale+95
        pdf.setPageSize((pw,ph));pdf.setFont('Helvetica-Bold',16);pdf.drawString(30,ph-26,f'Dvorak Symphony No. 8 | Trombone {page["part"]}')
        pdf.setFont('Helvetica',9);pdf.drawString(30,ph-42,f'Source PDF p.{pn} | C4 = middle C | H = B natural | b = flat | cue notes excluded')
        pdf.setFont('Helvetica',8);pdf.drawString(30,ph-55,'Blue = checked; amber = draft. Octave is a tiny pale-gray suffix; slide position is on the second line. Parentheses give alternate harmonics.')
        pdf.drawString(30,ph-67,'Standard Bb tenor trombone, no trigger. Lowest-numbered conventional harmonic is listed first; adjust position to instrument and tuning.')
        y=ph-82
        for strip in strips:
            sh=strip.height*scale;y-=sh;pdf.drawImage(ImageReader(strip),0,y,width=pw,height=sh)
        pdf.showPage()
    pdf.save()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--images',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--font',type=Path,required=True);a=p.parse_args();render(a.data,a.images,a.output,a.font)
