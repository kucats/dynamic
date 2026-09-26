#!/usr/bin/env python3
"""Build small, unreviewed ensemble phrase profiles from generated reader notes.

No audio, images, source PDFs or machine paths are copied. Run after build_reader.
Profiles are optional: the browser can fall back to the open part's notes.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def build(check=False):
    readers = [json.loads(p.read_text()) for p in sorted((ROOT / 'public/reader/data').glob('*.json'))]
    configs = {json.loads(p.read_text())['id']: p for p in ROOT.glob('project/**/dynamic/part.json')}
    marks_by_id = {key: json.loads(p.with_name('following.json').read_text())
                   for key, p in configs.items() if p.with_name('following.json').exists()}
    output = ROOT / 'public/reader/following'
    output.mkdir(exist_ok=True)
    for reader in readers:
        marks = marks_by_id.get(reader['id'], {})
        movements = {}
        used = {}
        for movement in reader['movements']:
            notes = []
            rehearsals = marks.get(movement['key'], [])
            primary_bars = {row[0]: row[1] for row in movement['timeline']}
            for peer in readers:
                if (peer['work'], peer['composer']) != (reader['work'], reader['composer']):
                    continue
                other = next((m for m in peer['movements'] if m['key'] == movement['key']), None)
                if not other or {r[0]: r[1] for r in other['timeline']} != primary_bars:
                    continue
                used[peer['id']] = {'sha256': peer['source']['sha256'], 'pages': peer['source']['pages']}
                if not rehearsals:
                    rehearsals = [dict(r, source_part=peer['id']) for r in marks_by_id.get(peer['id'], {}).get(movement['key'], [])]
                notes.extend([n['bar'], n['off'], n['dur'], n['snd'][2], bool(n['tie']), peer['id'], n['id']]
                             for n in peer['notes'] if n['mvt'] == movement['key'] and not n['unc'])
            assert all(1 <= r['bar'] <= movement['last'] and r['evidence'] for r in rehearsals)
            movements[movement['key']] = {'notes': notes, 'rehearsals': rehearsals, 'timeline': movement['timeline']}
        profile = {'schema': 2, 'id': reader['id'], 'audit': 'unreviewed', 'sources': used,
                   'limitations': 'Sparse ensemble template from available parts; uncertain notes and cues excluded. '
                                   'Playback timelines can omit repeats. No recording-to-measure ground truth.',
                   'movements': movements}
        path = output / f"{reader['id']}.json"
        text = json.dumps(profile, ensure_ascii=False, separators=(',', ':')) + '\n'
        if check:
            assert path.read_text() == text, f'Stale profile: {path.relative_to(ROOT)}'
        else:
            path.write_text(text)
        print(f"{reader['id']}: {len(used)} part(s), {sum(len(m['notes']) for m in movements.values())} notes")


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='verify reproducibility without writing')
    build(parser.parse_args().check)
