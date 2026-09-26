#!/usr/bin/env python3
"""Replay a local recording through the reader's actual phrase matcher.

Requires ffmpeg, NumPy and Node. Temporary decoded audio/spectra are deleted.
--out must be outside the repository: the trace is private derived audio data.
No accuracy is claimed without separately reviewed per-measure labels.
"""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SR, FFT, HOP = 48000, 8192, 9600


def extract(audio_path, directory, name, channel='mix'):
    pcm, spectra = directory / f'{name}.f32', directory / f'{name}-spectra.f32'
    channel_args = [] if channel == 'mix' else ['-af', f"pan=mono|c0=c{0 if channel == 'left' else 1}"]
    if channel == 'right':
        probe = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries',
                                'stream=channels', '-of', 'json', str(audio_path)], check=True, capture_output=True, text=True)
        if json.loads(probe.stdout)['streams'][0]['channels'] < 2:
            raise ValueError('right channel requires a recording with at least two channels')
    subprocess.run(['ffmpeg', '-v', 'error', '-i', str(audio_path), '-map', '0:a:0', *channel_args, '-ac', '1', '-ar', str(SR),
                    '-f', 'f32le', str(pcm)], check=True)
    audio = np.memmap(pcm, dtype='<f4', mode='r')
    n = np.arange(FFT)
    window = .42 - .5 * np.cos(2 * np.pi * n / FFT) + .08 * np.cos(4 * np.pi * n / FFT)
    with spectra.open('wb') as out:
        for end in range(HOP, len(audio) + 1, HOP):
            frame = audio[end - FFT:end]
            db = 20 * np.log10(np.maximum(1e-7, np.abs(np.fft.rfft(frame * window)[:-1]) / FFT))
            np.asarray([(end - FFT / 2) / SR, np.sqrt(np.mean(frame ** 2)), *db], dtype='<f4').tofile(out)
    return spectra, len(audio) / SR


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('audio', type=Path)
    p.add_argument('--part', default='dvorak8-trombone1')
    p.add_argument('--movement', default='IV')
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--node', default='node')
    p.add_argument('--reference', type=Path, help='diagnostic audio-to-audio comparison; never supplies score bars')
    p.add_argument('--reference-window', type=int, choices=[8, 16, 32], default=32)
    p.add_argument('--control', '--reference-control', dest='control', choices=['none', 'shuffle'], default='none')
    p.add_argument('--template', choices=['ensemble', 'part'], default='ensemble')
    p.add_argument('--features', choices=['chroma', 'harmonic'], default='chroma')
    p.add_argument('--tolerate-errors', action='store_true', help='diagnostic: cap negative evidence; never adds positive support')
    p.add_argument('--channel', choices=['mix', 'left', 'right'], default='mix')
    args = p.parse_args()
    if args.out.resolve().is_relative_to(ROOT):
        p.error('--out must be outside the repository')
    if args.part not in {x.stem for x in (ROOT / 'public/reader/data').glob('*.json')}:
        p.error('unknown part')
    if not args.reference and args.reference_window != 32:
        p.error('--reference-window requires --reference')
    if args.features == 'harmonic' and args.template != 'part':
        p.error('--features harmonic requires --template part')
    if args.tolerate_errors and args.features != 'harmonic':
        p.error('--tolerate-errors requires --features harmonic')
    if args.reference and (args.template != 'ensemble' or args.features != 'chroma' or args.tolerate_errors):
        p.error('reference-audio diagnostics do not use score-template/part-feature options')
    with tempfile.TemporaryDirectory(prefix='dynamic-follow-') as tmp:
        spectra, duration = extract(args.audio, Path(tmp), 'phone', args.channel)
        command = [args.node, str(Path(__file__).with_name('following_replay.mjs')), str(spectra), args.part, args.movement]
        reference_info = {}
        ref = ''
        if args.reference:
            ref, ref_duration = extract(args.reference, Path(tmp), 'reference')
            reference_info = {'reference_sha256': hashlib.sha256(args.reference.read_bytes()).hexdigest(),
                              'reference_decoded_seconds': ref_duration}
        command.extend([str(ref), str(args.reference_window), args.control, json.dumps({
            'template': args.template, 'features': args.features, 'tolerateErrors': args.tolerate_errors})])
        run = subprocess.run(command, check=True, capture_output=True, text=True)
        result = json.loads(run.stdout)
        result.update(audio_sha256=hashlib.sha256(args.audio.read_bytes()).hexdigest(),
                      decoded_seconds=duration, channel=args.channel,
                      extraction=f'mono {args.channel}; 48 kHz; 8192 Blackman FFT; 200 ms hop',
                      time_note='Trace timestamps are FFT-window centers; samples are available 85.333 ms later. '
                                'Sample-and-hold coverage is clipped at the final analyzed sample.',
                      measure_accuracy=None, accuracy_note='No independently reviewed audio-to-measure labels supplied. '
                                                         'Tracking fraction is coverage, not accuracy.')
        result.update(reference_info)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
        print(json.dumps({k: v for k, v in result.items() if k != 'trace'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
