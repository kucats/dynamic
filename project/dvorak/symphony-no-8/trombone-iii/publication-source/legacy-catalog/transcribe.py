import argparse,csv,hashlib,json,zipfile,xml.etree.ElementTree as ET
from pathlib import Path

EXPECTED_SOURCE_SHA256='6c161bf1a3a10e54194fecec8b52e2bc6a6fa0de7638c21296808e5456719d8c'
EXPECTED_OMR_SHA256='ddd6a3b21c832c1ba0a84f6df348d2c42a201c8aca9077474b5e5e961f57d3a9'

def sha256_file(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''): digest.update(block)
    return digest.hexdigest()

ALPHA='CDEFGAB'
NAT={'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}
SHARP_ORDER='FCGDAEB'; FLAT_ORDER='BEADGCF'
ALTER={'SHARP':1,'FLAT':-1,'NATURAL':0,'DOUBLE_SHARP':2,'DOUBLE_FLAT':-2,'FLAT_FLAT':-2,'SHARP_SHARP':2}
HARM={2:12,3:19,4:24,5:28,6:31,7:34,8:36,9:38,10:40}

def key_alter(letter,fifths):
    if fifths>0 and letter in SHARP_ORDER[:fifths]: return 1
    if fifths<0 and letter in FLAT_ORDER[:-fifths]: return -1
    return 0

MIDLINE={'ALTO':28,'TENOR':26,'BASS':22,'TREBLE':34} # diatonic C0=0; matching read_omr.py

def diatonic(step,clef='BASS'):
    idx=MIDLINE[clef]-int(step) # Audiveris staff steps increase downward from each clef's middle line.
    octave,letter_index=divmod(idx,7)
    return ALPHA[letter_index],octave

def midi_for(letter,octave,alter): return 12*(octave+1)+NAT[letter]+alter

def pitch_label(letter,octave,alter):
    name='H' if letter=='B' and alter==0 else ('B' if letter=='B' and alter<0 else letter)
    suffix={-2:'bb',-1:'b',0:'',1:'#',2:'##'}.get(alter,'?')
    return f'{name}{suffix}{octave}'

def positions(midi):
    # Same open Bb trombone harmonic lookup used for TB2 (partials 2-10).
    out=[]
    for pos in range(1,8):
        base=34-(pos-1) # Bb1 in first position.
        for partial,interval in HARM.items():
            if base+interval==midi:
                out.append(str(pos)); break
    if not out:
        # F-attachment side, six usable positions; Yamaha notes these are farther out and instrument-specific.
        for pos in range(1,7):
            base=29-(pos-1) # F1 in first position.
            if any(base+interval==midi for interval in HARM.values()): out.append(f'{pos}F')
    return out

def refs_text(parent,tag):
    e=parent.find(tag)
    return (e.text or '').split() if e is not None else []

def get_bounds_x(obj):
    b=obj.find('bounds') if obj is not None else None
    return float(b.get('x'))+float(b.get('w'))/2 if b is not None else None

def extract(omr_path,source_sha,out_json,out_csv):
    if source_sha.lower()!=EXPECTED_SOURCE_SHA256:
        raise ValueError('source PDF hash does not match the reviewed part')
    if sha256_file(omr_path)!=EXPECTED_OMR_SHA256:
        raise ValueError('OMR archive hash does not match the reviewed recognition project')
    entries=[];pages=[];key_state=1
    with zipfile.ZipFile(omr_path) as z:
      for page_no in range(10,14):
        root=ET.fromstring(z.read(f'sheet#{page_no}/sheet#{page_no}.xml'))
        objs={e.get('id'):e for e in root.iter() if e.get('id')}
        head_objs={e.get('id'):e for e in root.iter('head') if e.get('id')}
        page_systems=[]
        alter_for={}
        for rel in root.iter('relation'):
            if rel.find('alter-head') is not None:
                src=objs.get(rel.get('source')); dst=rel.get('target')
                if src is not None and src.tag=='alter': alter_for[dst]=ALTER.get(src.get('shape',''),0)
        chord_heads={}
        for rel in root.iter('relation'):
            if rel.find('containment') is not None:
                src,dst=rel.get('source'),rel.get('target')
                if dst in head_objs: chord_heads.setdefault(src,[]).append(dst)
        for si,system in enumerate(root.iter('system'),1):
            staves=list(system.iter('staff'))
            for staff in staves:
                staff_num=None
                # Head.staff numbers are sequential per score line; use clef/key staff or local system index.
                head_ids=(staff.findtext('notes') or '').split()
                valid=[head_objs[x] for x in head_ids if x in head_objs]
                if not valid: continue
                staff_num=valid[0].get('staff')
                head_ids=[x for x in head_ids if x in head_objs]
                # inherit one-sharp G major at start; update on printed key signature changes.
                header=staff.find('header')
                if header is not None:
                    for keyid in refs_text(header,'key'):
                        k=objs.get(keyid)
                        if k is not None and k.get('fifths') is not None: key_state=int(float(k.get('fifths')))
                clef='BASS'
                if header is not None:
                    for clefid in refs_text(header,'clef'):
                        c=objs.get(clefid)
                        if c is not None: clef=c.get('kind','BASS')
                # Determine barline x boundaries and any mid-system key changes.
                boundaries=[]; key_events=[]
                for measure in system.iter('measure'):
                    right_barline=measure.find('right-barline')
                    for bid in refs_text(right_barline if right_barline is not None else ET.Element('x'),'staff-barlines'):
                        bobj=objs.get(bid)
                        if bobj is not None and bobj.get('staff')==staff_num:
                            x=get_bounds_x(bobj)
                            if x is not None: boundaries.append(x)
                    for kid in refs_text(measure,'keys'):
                        k=objs.get(kid)
                        if k is not None and k.get('fifths') is not None:
                            x=get_bounds_x(k)
                            if x is not None: key_events.append((x,int(float(k.get('fifths')))))
                boundaries=sorted(set(boundaries)); key_events.sort()
                lines=staff.find('lines').findall('line')
                lineys=[sum(float(p.get('y')) for p in l.findall('point'))/len(l.findall('point')) for l in lines]
                interline=sum(lineys[i+1]-lineys[i] for i in range(4))/4
                row_notes=[]
                for hid in head_ids:
                    h=head_objs[hid]; b=h.find('bounds')
                    x=float(b.get('x'))+float(b.get('w'))/2; y=float(b.get('y'))+float(b.get('h'))/2
                    row_notes.append((x,y,h,b))
                row_notes.sort(key=lambda v:(v[0],v[1]))
                # Map detected noteheads to a score voice. Voice 1 is the part line; other voices are cues.
                voice_by_head={}
                for measure in system.iter('measure'):
                    for voice in measure.iter('voice'):
                        for val in voice.iter('value'):
                            chord=val.get('chord')
                            for hid in chord_heads.get(chord,[]): voice_by_head[hid]=int(voice.get('id','1'))
                accidental_state={};bi=0;current_key=key_state;ki=0
                system_noteids=[]
                left=float(staff.get('left','0'))
                for x,y,h,b in row_notes:
                    while bi<len(boundaries) and x>boundaries[bi]:
                        bi+=1; accidental_state={}
                    while ki<len(key_events) and x>=key_events[ki][0]:
                        current_key=key_events[ki][1];accidental_state={};ki+=1
                    raw_step=int(float(h.get('pitch','0')))
                    letter,octave=diatonic(raw_step,clef)
                    explicit=alter_for.get(h.get('id'))
                    if explicit is not None:
                        alteration=explicit; accidental_state[(letter,octave)]=explicit
                    else:
                        alteration=accidental_state.get((letter,octave),key_alter(letter,current_key))
                    midi=midi_for(letter,octave,alteration)
                    pos=positions(midi)
                    hid=h.get('id');voice=voice_by_head.get(hid)
                    # Voice-2 detections can be cues or legitimate second-voice notes; keep them amber in the guide.
                    role='play'
                    lowgrade=float(h.get('ctx-grade',h.get('grade','1')))
                    status='omr_high_confidence' if lowgrade>=0.65 and voice==1 else 'needs_review'
                    # All labels are score-derived; unmatched voices and weak notehead recognition remain amber.
                    noteid=f'p{page_no:02d}-s{si:02d}-h{hid}'
                    note={'id':noteid,'page':page_no,'part':3,'system':si,'bar_slot':bi+1,'source_head_id':hid,
                          'x':x/2850,'y':y/3749,'bbox':[float(b.get('x'))/2850,float(b.get('y'))/3749,float(b.get('w'))/2850,float(b.get('h'))/3749],
                          'omr_staff_step':raw_step,'clef':clef,'key_fifths':current_key,'omr_explicit_alter':explicit,
                          'step':letter,'alter':alteration,'octave':octave,'role':role,'voice_id':voice,
                          'status':status,'omr_grade':lowgrade,'onset_seconds':None,'duration_seconds':None,
                          'pitch':pitch_label(letter,octave,alteration),'german_pitch':pitch_label(letter,octave,alteration),
                          'midi':midi,'pitch_source':'Audiveris staff position + key/accidental; visual review pending',
                          'slide_positions':pos,'recommended_slide_position':pos[0] if pos else '?'}
                    entries.append(note);system_noteids.append(noteid)
                key_state=current_key
                page_systems.append({'system':si,'top':min(lineys)/3749,'bottom':max(lineys)/3749,'interline':interline/3749,
                                     'notes':[n['id'] for n in entries if n['page']==page_no and n['system']==si and n['role']=='play'],
                                     'key_fifths':current_key,'clef':'BASS','reviewed':False})
        pages.append({'page':page_no,'part':3,'width':2850,'height':3749,'systems':page_systems})
        # key signatures carry across systems/pages; all observed transitions are captured above.
    # Regression anchor: printed rehearsal C in TB3 begins D3-G3-E3, slides 4-4-2.
    anchor=sorted((n for n in entries if n['page']==10 and n['system']==2 and n['voice_id']==1 and .62<=n['x']<=.71),key=lambda n:n['x'])
    assert [n['pitch'] for n in anchor]==['D3','G3','E3'], f'rehearsal C pitch anchor mismatch: {[n["pitch"] for n in anchor]}'
    assert [n['recommended_slide_position'] for n in anchor]==['4','4','2'], f'rehearsal C slide anchor mismatch: {[n["recommended_slide_position"] for n in anchor]}'
    data={'schema':'source-pitch-reading-v1','work':'Dvorak Symphony No. 8, Op. 88','selected_part':3,
          'source_sha256':source_sha,'omr_sha256':'ddd6a3b21c832c1ba0a84f6df348d2c42a201c8aca9077474b5e5e961f57d3a9',
          'omr_version':'5.11.0','octave_convention':'C4=middle C, MIDI60','timing_status':'not_aligned',
          'clef_note':'Bass clef assumed on source p.10 where Audiveris missed the printed clef; confirmed on p.11-13.',
          'cue_note_policy':'All detected noteheads are shown. Voice-2 or unresolved-voice noteheads are amber cue candidates; confirm their role before playing.',
          'pages':pages,'notes':entries,
          'slide_position_method':{'instrument':'Bb trombone open side; F-attachment fallback for notes with no open-side position',
             'reference':'position 1 practical Bb2 = MIDI46; partials 2-10 rounded to equal temperament, matching TB2 reading',
             'low_note':'F-attachment positions are marked 1F-6F where required; confirm against actual instrument and tuning.',
             'order':'shortest conventional open slide first; alternate positions follow; amber cue candidates remain for reference.'}}
    Path(out_json).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    fields=['id','page','system','bar_slot','role','voice_id','pitch','midi','recommended_slide_position','slide_positions','status','source_head_id']
    with Path(out_csv).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
        for n in entries:w.writerow({**n,'slide_positions':';'.join(n['slide_positions'])})
    play=[n for n in entries if n['role']=='play'];reviewvoice=[n for n in play if n['voice_id']!=1]
    print(f'heads={len(entries)} shown={len(play)} voice_or_pitch_review={sum(n["status"]=="needs_review" for n in play)} voice2_or_unassigned={len(reviewvoice)} no_position={sum(not n["slide_positions"] for n in play)}')
    print('pitch_range',min(n['midi'] for n in play),max(n['midi'] for n in play))
    print('review',sum(n['status']=='needs_review' for n in play),'systems',len(pages))
    print('key signatures by system')
    for p in pages: print(p['page'],[(s['system'],s['key_fifths']) for s in p['systems']])

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--omr',required=True);ap.add_argument('--source-sha',required=True);ap.add_argument('--json',required=True);ap.add_argument('--csv',required=True);a=ap.parse_args();extract(a.omr,a.source_sha,a.json,a.csv)
