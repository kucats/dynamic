"""Synthetic-only score fixtures; no private score, review or source path is committed."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from tools.fuyomi.cli import main
from tools.fuyomi.score import CLEFS, TPQ, apply_corrections, attach_rhythm, pitch_info, playback_events, read_omr
from tools.fuyomi import workflow as w

OPTIONAL = all(importlib.util.find_spec(name) for name in ('PIL', 'pypdf', 'reportlab'))
REVIEW = {'status': 'source_checked', 'by': 'synthetic fixture', 'note': 'Authored test pitches and durations'}


def synthetic_omr(path, *, clef='ALTO', extra_staff=False):
    lines = ''.join(f'<line><point x="50" y="{y}"/><point x="750" y="{y}"/></line>' for y in range(150, 191, 10))
    staff = f'<staff><lines>{lines}</lines></staff>'
    # C4, C4, D#4, E5 cue. The explicit sharp is attached to head 3.
    heads = ''.join(f'<head id="{i}" pitch="{p}" grade="0.9"><bounds x="{x-8}" y="{170+p*5-6}" w="16" h="12"/></head>'
                    for i, x, p in [(1, 180, 0), (2, 280, 0), (3, 450, -1), (4, 650, -9)])
    clef_xml = f'<clef id="20" kind="{clef}"><bounds x="60" y="145" w="20" h="40"/></clef>'
    xml = (f'<sheet><system id="1"><part>{staff}{staff if extra_staff else ""}</part><sig><inters>{clef_xml}{heads}'
           '<alter id="21" shape="SHARP"><bounds x="430" y="157" w="10" h="16"/></alter>'
           '<staff-barline id="22"><bounds x="350" y="150" w="2" h="40"/></staff-barline>'
           '</inters><relations><relation source="21" target="3"><alter-head/></relation></relations></sig></system></sheet>')
    with zipfile.ZipFile(path, 'w') as archive:
        archive.writestr('sheet#1/sheet#1.xml', xml)


def make_workspace(parent):
    from PIL import Image, ImageDraw
    from reportlab.pdfgen import canvas
    from reportlab.lib.utils import ImageReader
    image = Image.new('RGB', (800, 400), 'white')
    draw = ImageDraw.Draw(image)
    for y in range(150, 191, 10):
        draw.line((50, y, 750, y), fill='black', width=1)
    for x, y in [(180, 170), (280, 170), (450, 165), (570, 155)]:
        draw.ellipse((x-8, y-5, x+8, y+5), fill='black')
        draw.line((x+8, y, x+8, y-35), fill='black', width=2)
    draw.text((50, 40), 'Synthetic score / C4 tie, D4, F4', fill='black')
    source = parent/'source.pdf'
    pdf = canvas.Canvas(str(source), pagesize=(800, 400), invariant=1)
    pdf.drawImage(ImageReader(image), 0, 0, width=800, height=400)
    pdf.save()
    root = parent/'workspace'
    w.init_workspace(source, root, [1], title='Synthetic part', part='Trombone', clef='ALTO', fifths=0, meter=[4,4], image_mode='embedded')
    omr = parent/'one.omr'
    synthetic_omr(omr)
    w.import_omr(root, {1: omr}, 'synthetic')
    c, r = w.read_json(root/'corrections.json'), w.read_json(root/'rhythm.json')
    c['pages']['1']['1'] = {'review': REVIEW, 'remove': [4], 'replace': {'3':'D4'},
                            'add': [{'x':570,'y':155,'pitch':'F4','clef':'ALTO'}], 'reason':'Exclude synthetic cue; correct accidental; restore missing head'}
    r['pages']['1']['1'] = {'review': REVIEW, 'tokens':'2~ 2 | 1 r1 2 | R2'}
    r['repeat_regions'] = [{'start':[1,1,3], 'end':[1,1,3]}]
    w.write_json(root/'corrections.json', c)
    w.write_json(root/'rhythm.json', r)
    return root, source


class ScoreTest(unittest.TestCase):
    def test_pitch_conventions_and_basic_positions(self):
        self.assertEqual(pitch_info('B3'), (59, 27, 'H3'))
        self.assertEqual(pitch_info('Bb3'), (58, 27, 'Bb3'))
        self.assertEqual(pitch_info('C4'), (60, 28, 'C4'))
        for value in ('H3', 'C', 'C#b4', 'C12'):
            with self.assertRaises(ValueError): pitch_info(value)

    def test_clefs_accidental_and_geometry(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'test.omr'
            for clef, expected in [('ALTO','C4'),('TENOR','A3'),('BASS','D3'),('TREBLE','B4'),('BARITONE','F3')]:
                synthetic_omr(path, clef=clef)
                systems=read_omr(path,default_clef='ALTO',default_fifths=0)
                self.assertEqual(systems[0]['notes'][0]['pitch'],expected)
                self.assertEqual(systems[0]['notes'][0]['geometry_residual'],0)
                self.assertEqual(systems[0]['notes'][0]['grade'],0.9)
            synthetic_omr(path)
            self.assertEqual(read_omr(path,default_clef='ALTO',default_fifths=0)[0]['notes'][2]['pitch'],'D#4')
            synthetic_omr(path,extra_staff=True)
            with self.assertRaisesRegex(ValueError,'one played staff'): read_omr(path,default_clef='ALTO',default_fifths=0)

    def test_system_clef_correction_recomputes_candidate_pitch(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'test.omr'
            synthetic_omr(path,clef='BASS')
            systems=read_omr(path,default_clef='BASS',default_fifths=0)
            candidates={'default_clef':'BASS','pages':{'1':systems}}
            corrections={'pages':{'1':{'1':{'review':{'status':'unreviewed'},'remove':[],'replace':{},'add':[],
                                             'clef':'TREBLE','reason':'Printed clef was missed by OMR'}}}}
            pages,issues=apply_corrections(candidates,corrections)
            note=pages['1'][0]['notes'][0]
            self.assertEqual(note['raw_pitch'],'D3')
            self.assertEqual(note['pitch'],'B4')
            self.assertEqual(note['raw_clef'],'BASS')
            self.assertEqual(note['clef'],'TREBLE')
            self.assertAlmostEqual(note['review_geometry_residual'],0)
            self.assertEqual(issues[0]['kind'],'unreviewed_pitch')

    def test_system_key_correction_recomputes_candidate_pitch(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'test.omr'
            synthetic_omr(path)
            with zipfile.ZipFile(path) as archive: xml=archive.read('sheet#1/sheet#1.xml').decode()
            xml=xml.replace('pitch="0"','pitch="-3"').replace('pitch="-1"','pitch="-3"').replace('pitch="-9"','pitch="-3"')
            xml=xml.replace('<alter id="21" shape="SHARP"><bounds x="430" y="157" w="10" h="16"/></alter>','')
            xml=xml.replace('<relation source="21" target="3"><alter-head/></relation>','')
            with zipfile.ZipFile(path,'w') as archive: archive.writestr('sheet#1/sheet#1.xml',xml)
            systems=read_omr(path,default_clef='ALTO',default_fifths=0)
            self.assertEqual([n['pitch'] for n in systems[0]['notes']],['F4']*4)
            candidates={'default_clef':'ALTO','pages':{'1':systems}}
            corrections={'pages':{'1':{'1':{'review':{'status':'unreviewed'},'remove':[],'replace':{},'add':[],
                                             'fifths':1,'reason':'Key signature in this system is one sharp'}}}}
            pages,issues=apply_corrections(candidates,corrections)
            self.assertEqual([n['pitch'] for n in pages['1'][0]['notes']],['F#4']*4)
            self.assertTrue(issues)

    def test_key_and_accidental_carry_reset_at_bar(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'test.omr'
            synthetic_omr(path)
            with zipfile.ZipFile(path) as z: xml=z.read('sheet#1/sheet#1.xml').decode()
            # Make all heads F4. First accidental natural cancels F# through head 2;
            # bar at 350 resets the key, head 3 sharp then carries to head 4.
            xml=xml.replace('pitch="0" grade','pitch="-3" grade').replace('pitch="-1" grade','pitch="-3" grade').replace('pitch="-9" grade','pitch="-3" grade')
            xml=xml.replace('</inters>','<alter id="30" shape="NATURAL"><bounds x="150" y="140" w="10" h="20"/></alter></inters>')
            xml=xml.replace('</relations>','<relation source="30" target="1"><alter-head/></relation></relations>')
            with zipfile.ZipFile(path,'w') as z:z.writestr('sheet#1/sheet#1.xml',xml)
            systems=read_omr(path,default_clef='ALTO',default_fifths=1)
            self.assertEqual([n['pitch'] for n in systems[0]['notes']],['F4','F4','F#4','F#4'])
            candidates={'default_clef':'ALTO','pages':{'1':systems}}
            corrections={'pages':{'1':{'1':{'review':{'status':'unreviewed'},'remove':[],'replace':{},'add':[],
                                             'fifths':0,'reason':'Key signature cancellation in the system'}}}}
            pages,_=apply_corrections(candidates,corrections)
            self.assertEqual([n['pitch'] for n in pages['1'][0]['notes']],['F4','F4','F#4','F#4'])

    def test_tuplets_exact_and_invalid_rhythm_fails(self):
        notes=[{'note_id':str(i),'pitch':'C4','midi':60} for i in range(3)]
        pages={'1':[{'system':1,'notes':notes}]}
        rhythm={'pages':{'1':{'1':{'tokens':'1/3 1/3 1/3 r3','review':REVIEW}}}}
        movements=[{'id':1,'pages':[1],'meter':[4,4]}]
        timing,issues=attach_rhythm(deepcopy(pages),rhythm,movements)
        self.assertFalse(issues)
        self.assertEqual([e['duration_ticks'] for e in timing['events']],[160,160,160,1440])
        for bad in ('1/7 1/7 1/7 r25/7','0 2 2','1~ r1 1 1','1 1 1','-1 1 4','R0'):
            rhythm['pages']['1']['1']['tokens']=bad
            with self.assertRaises(ValueError,msg=bad):attach_rhythm(deepcopy(pages),rhythm,movements)

    def test_system_boundary_meter_change(self):
        pages={'1':[{'system':1,'notes':[{'note_id':f'a{i}','pitch':'C4','midi':60} for i in range(4)]}],
               '2':[{'system':1,'notes':[{'note_id':f'b{i}','pitch':'D4','midi':62} for i in range(3)]}]}
        rhythm={'pages':{'1':{'1':{'review':REVIEW,'tokens':'1 1 1 1'}},
                         '2':{'1':{'review':REVIEW,'tokens':'1 1 1'}}}}
        movement={'id':1,'pages':[1,2],'meter':[4,4],
                  'meter_changes':[{'start':[2,1],'meter':[3,4]}]}
        timing,issues=attach_rhythm(deepcopy(pages),rhythm,[movement])
        self.assertFalse(issues)
        self.assertEqual(timing['movement_ticks'][1],7*TPQ)
        self.assertEqual(timing['movement_written_bars'][1],2)
        self.assertEqual(timing['events'][4]['onset_ticks'],4*TPQ)
        movement['meter_changes']=[{'start':[2,2],'meter':[3,4]}]
        with self.assertRaisesRegex(ValueError,'selected system'):
            attach_rhythm(deepcopy(pages),rhythm,[movement])

    def test_repeats_endings_and_no_repeat_policy(self):
        events=[{'page':1,'system':1,'group':i,'movement':1,'kind':'rest','onset_ticks':(i-1)*480,'duration_ticks':480} for i in range(1,5)]
        timing={'events':events,'repeat_regions':[{'start':[1,1,1],'end':[1,1,2],'first_ending':[1,1,2],'second_ending':[1,1,3]}]}
        self.assertEqual([e['group'] for e in playback_events(timing,1,True)],[1,2,1,3,4])
        self.assertEqual([e['group'] for e in playback_events(timing,1,False)],[1,3,4])
        timing['repeat_regions'].append({'start':[1,1,2],'end':[1,1,4]})
        with self.assertRaisesRegex(ValueError,'overlapping'):playback_events(timing,1,True)
        timing['repeat_regions']=[{'start':[1,1,9],'end':[1,1,9]}]
        with self.assertRaisesRegex(ValueError,'coordinates'):playback_events(timing,1,False)

    def test_page_parser_and_path_boundary(self):
        self.assertEqual(w.parse_pages('2-4,6'),[2,3,4,6])
        for value in ('0','4-2','1,1','3,1'):
            with self.assertRaises(ValueError):w.parse_pages(value)
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            with self.assertRaises(ValueError):w.local_path(root,'../escape')
            (root/'link').symlink_to(root/'inside')
            with self.assertRaises(ValueError):w.local_path(root,'link/file')

@unittest.skipUnless(OPTIONAL,'optional fuyomi dependencies not installed')
class WorkflowTest(unittest.TestCase):
    def test_end_to_end_rebuild_bundle_and_stale_guards(self):
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory)
            root,source=make_workspace(parent)
            original=w.sha256(source)
            result=w.build(root)
            out=Path(result['output'])
            self.assertEqual(result['status'],'source_checked')
            score=w.read_json(out/'score.json')
            self.assertEqual(score['audit']['note_count'],4)
            self.assertEqual(score['audit']['tie_count'],1)
            self.assertEqual(score['audit']['removed_candidates'],1)
            self.assertEqual(score['audit']['added_notes'],1)
            self.assertEqual(score['audit']['pitch_corrections'],1)
            self.assertEqual(score['timing']['movement_ticks']['1'],16*TPQ)
            self.assertEqual(len(score['playback']['1']['repeats']),7)
            self.assertTrue(w.build(root)['cached'])
            self.assertEqual(w.sha256(source),original)
            self.assertEqual(w.validate(root,source=source)['build_artifacts'],'passed')
            pdf=PdfReader(out/'reading.pdf')
            self.assertEqual(len(pdf.pages),1)
            self.assertFalse(any(page.get('/Annots') for page in pdf.pages))
            html=(out/'reading.html').read_text()
            self.assertIn('.halo{fill:none;',html)
            self.assertIn('id="play"',html)
            self.assertNotIn('__DATA__',html)
            from tools.fuyomi.render import render_candidate_review
            candidate_html=render_candidate_review(root).read_text()
            self.assertIn('Audiveris grade 0.900',candidate_html)
            self.assertIn('正しさを示す確率',candidate_html)
            bundle=parent/'bundle.zip';w.bundle(root,bundle)
            with zipfile.ZipFile(bundle) as z:
                rebuild=z.read('fuyomi/REBUILD.txt').decode()
                self.assertIn('Install Python 3.11+',rebuild)
                self.assertNotIn('vEdit',rebuild)
                z.extractall(parent/'unpacked')
            restored=parent/'unpacked/fuyomi'
            self.assertEqual(w.validate(restored)['build_artifacts'],'passed')
            self.assertTrue(w.build(restored)['cached'])
            # Rebuild with cache removed: deterministic score, HTML and PDF bytes.
            before={name:w.sha256(out/name) for name in ['score.json','reading.html','reading.pdf']}
            shutil.rmtree(restored/'builds')
            rebuilt=Path(w.build(restored)['output'])
            self.assertEqual(before,{name:w.sha256(rebuilt/name) for name in before})
            corrections=w.read_json(root/'corrections.json')
            corrections['pages']['1']['1']['review']['note']='Updated evidence'
            w.write_json(root/'corrections.json',corrections)
            with self.assertRaisesRegex(ValueError,'stale'):w.validate(root)

    def test_input_and_output_tampering_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root,_=make_workspace(Path(directory));result=w.build(root)
            out=Path(result['output']);(out/'reading.html').write_text('changed')
            with self.assertRaisesRegex(ValueError,'artifact checksum'):w.build(root)
            candidates=w.read_json(root/'candidates.json');candidates['pages']['1'][0]['notes'][0]['pitch']='C3'
            w.write_json(root/'candidates.json',candidates)
            with self.assertRaisesRegex(ValueError,'binding is stale'):w.compile_score(root)

    def test_review_status_is_distinct_from_structural_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root,_=make_workspace(Path(directory))
            c=w.read_json(root/'corrections.json');c['pages']['1']['1']['review']['status']='unreviewed';w.write_json(root/'corrections.json',c)
            data,audit,_=w.compile_score(root)
            self.assertEqual(audit['structural_checks'],'passed')
            self.assertEqual(audit['review_status'],'needs_review')
            with patch('builtins.print'):
                self.assertEqual(main(['fuyomi','validate',str(root),'--strict']),2)
            p=w.read_json(root/'project.json');p['movements'][0]['expected_written_bars']=99;w.write_json(root/'project.json',p)
            self.assertIn('bar_count',[i['kind'] for i in w.compile_score(root)[1]['issues']])

    def test_title_does_not_escape_script_or_html(self):
        with tempfile.TemporaryDirectory() as directory:
            root,_=make_workspace(Path(directory))
            p=w.read_json(root/'project.json');p['title']='</script><script>alert(1)</script> __ROWS__';w.write_json(root/'project.json',p)
            out=Path(w.build(root)['output']);html=(out/'reading.html').read_text()
            self.assertEqual(html.count('<script>'),1)
            self.assertIn('\\u003c/script\\u003e',html)
            self.assertIn('&lt;/script&gt;',html)
            self.assertIn('__ROWS__',html)  # User title tokens remain literal.

    def test_cache_recognition_skips_completed_pages(self):
        with tempfile.TemporaryDirectory() as directory:
            parent=Path(directory);root,_=make_workspace(parent)
            # Use a copy with imported/review stages removed; images stay immutable.
            for name in ['recognition.json','candidates.json','corrections.json','rhythm.json']:(root/name).unlink()
            shutil.rmtree(root/'recognition')
            executable=parent/'fake-audiveris';executable.write_text('synthetic executable identity')
            def fake_run(command,**kwargs):
                destination=Path(command[command.index('-output')+1])
                synthetic_omr(destination/'page-0001.omr')
                return type('Result',(),{'returncode':0})()
            with patch('tools.fuyomi.workflow.subprocess.run',side_effect=fake_run) as run:
                w.recognize(root,executable,'test')
                self.assertEqual(run.call_count,1)
            for name in ['recognition.json','candidates.json','corrections.json','rhythm.json']:(root/name).unlink()
            shutil.rmtree(root/'recognition')
            with patch('tools.fuyomi.workflow.subprocess.run') as run:
                w.recognize(root,executable,'test')
                run.assert_not_called()


if __name__=='__main__':unittest.main()
