"""Render review strips and a PDF from source-coordinate pitch records."""
import argparse,json,re
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

def pitch_parts(label):
    match=re.fullmatch(r'(.+?)(-?\d+)',label)
    return (match.group(1),match.group(2)) if match else (label,'')

def render(data,images,out,font_regular,font_bold):
    doc=json.loads(data.read_text());notes={n['id']:n for n in doc['notes']};out.mkdir(parents=True,exist_ok=True)
    pdf=canvas.Canvas(str(out/'dvorak8-trombone3-pitch-reading-with-positions.pdf'))
    pdf.setTitle('Dvorak 8 - Trombone III - concert pitch reading')
    pitch_font=ImageFont.truetype(str(font_bold),44)
    position_font=ImageFont.truetype(str(font_bold),40)
    source_font=ImageFont.truetype(str(font_regular),19)
    octave_font=ImageFont.truetype(str(font_regular),12)
    lane_height=96
    for page in doc['pages']:
        pn=page['page'];im=Image.open(images/f'page-{pn:02d}.jpg').convert('RGB');w,h=im.size
        strips=[]
        for i,sys in enumerate(page['systems']):
            top=int(sys['top']*h);bottom=int(sys['bottom']*h)
            y0=int((page['systems'][i-1]['bottom']*h+top)/2) if i else max(0,top-180)
            y1=int((bottom+page['systems'][i+1]['top']*h)/2) if i+1<len(page['systems']) else bottom+50
            ns=sorted([notes[x] for x in sys['notes'] if notes[x]['role']=='play'],key=lambda n:n['x'])
            lanes=[];ends=[]
            for n in ns:
                label=n['german_pitch'];x=n['x']*w
                pitch,octave=pitch_parts(label)
                position=str(n['recommended_slide_position'])
                pitch_width=pitch_font.getlength(pitch)+octave_font.getlength(octave)+(3 if octave else 0)
                length=max(pitch_width,position_font.getlength(position))
                lane=next((j for j,e in enumerate(ends) if x-length/2>e+10),len(ends))
                if lane==len(ends): ends.append(0)
                ends[lane]=x+length/2;lanes.append((n,lane))
            score_height=y1-y0
            label_height=20+len(ends)*lane_height if ends else 35
            strip=Image.new('RGB',(w,score_height+label_height),'white');strip.paste(im.crop((0,y0,w,y1)),(0,0));d=ImageDraw.Draw(strip)
            d.line((120,score_height,w-100,score_height),fill='#d9e4ea',width=1)
            d.text((12,score_height+7),f'p{pn} / s{sys["system"]}',font=source_font,fill='#516779')
            for n,lane in lanes:
                x=n['x']*w;y=n['y']*h-y0;ly=score_height+6+lane*lane_height
                pitch,octave=pitch_parts(n['german_pitch'])
                position=str(n['recommended_slide_position'])
                color='#075d82' if n['status']=='omr_high_confidence' else '#a55710'
                d.ellipse((x-9,y-8,x+9,y+8),outline=color,width=1)
                d.line((x,y+12,x,ly),fill='#c6cdd1',width=1)
                pitch_width=pitch_font.getlength(pitch)
                octave_width=octave_font.getlength(octave)
                text_width=pitch_width+octave_width+(3 if octave else 0)
                text_x=x-text_width/2
                d.text((text_x,ly),pitch,anchor='lt',font=pitch_font,fill=color)
                if octave:
                    d.text((text_x+pitch_width+3,ly+6),octave,anchor='lt',font=octave_font,fill='#b8c0c4')
                d.text((x,ly+47),position,anchor='mt',font=position_font,fill=color)
            strip.save(out/f'qa-p{pn:02d}-s{sys["system"]:02d}.png');strips.append((sys['system'],strip))
        pw=850;scale=pw/w
        for start in range(0,len(strips),3):
            group=strips[start:start+3]
            ph=sum(strip.height for _,strip in group)*scale+105
            pdf.setPageSize((pw,ph));pdf.setFont('Helvetica-Bold',18);pdf.drawString(30,ph-27,'Dvorak Symphony No. 8 | Trombone III')
            systems=f'{group[0][0]}-{group[-1][0]}' if len(group)>1 else str(group[0][0])
            pdf.setFont('Helvetica',10);pdf.drawString(30,ph-44,f'Source PDF p.{pn}, systems {systems} | C4 = middle C | H = B natural | b = flat')
            pdf.setFont('Helvetica',9);pdf.drawString(30,ph-58,'Large pitch and primary slide position beneath each note. Tiny pale digit = octave.')
            pdf.drawString(30,ph-71,'Blue = high OMR confidence; amber = check pitch/voice and possible cue before playing.')
            pdf.drawString(30,ph-84,'Open positions 1-7; F suffix = F attachment. Alternate positions are retained in the CSV.')
            y=ph-98
            for _,strip in group:
                sh=strip.height*scale;y-=sh;pdf.drawImage(ImageReader(strip),0,y,width=pw,height=sh)
            pdf.showPage()
    pdf.save()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--images',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--font-regular',type=Path,required=True);p.add_argument('--font-bold',type=Path,required=True);a=p.parse_args();render(a.data,a.images,a.output,a.font_regular,a.font_bold)
