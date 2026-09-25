"""Measure-memo browser regression using public derivatives + synthetic API only.

python tests/reader/memo-browser.py --out /tmp/memo-evidence
Install Python Playwright and its Chromium first. --browser overrides executable.
--offline uses an inline source harness for restricted containers (not module-loading evidence).
No production server, Google login, R2, credentials or private memos are accessed.
"""
from __future__ import annotations

import argparse
import functools
import json
import re
import threading
from copy import deepcopy
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
READER = ROOT / 'public/reader'
PART = 'dvorak8-trombone1'
TIME = '2026-09-25T00:00:00.000Z'
BASE = {'id': 'legacy', 'text': '息をしっかり吸う。ここから丁寧に。', 'kind': 'issue',
        'rehearsal': 'H', 'anchor': {'mvt': 'I', 'bar': 59, 'page': 1, 'sys': 1, 'x': 300, 'y': 20},
        'createdAt': TIME, 'updatedAt': TIME}


class Fixture:
    def __init__(self, part=PART):
        self.part = part
        self.memos = [deepcopy(BASE), {**deepcopy(BASE), 'id': 'unknown', 'anchor': {'mvt': 'I', 'bar': 999}},
                      {**deepcopy(BASE), 'id': 'other-movement', 'anchor': {'mvt': 'IV', 'bar': 59}}]
        self.calls = []
        self.logged_in, self.enabled, self.fail = True, True, 0

    def api(self, path, method='GET', body=None):
        path = urlsplit(path).path
        self.calls.append({'path': path, 'method': method, 'body': body})
        if path == '/api/me':
            return {'status': 200, 'body': {'enabled': self.enabled, 'loggedIn': self.logged_in,
                    'email': 'practice@example.invalid', 'memoParts': [self.part]}}
        if self.fail and method != 'GET':
            status, self.fail = self.fail, 0
            return {'status': status, 'body': {'error': 'テスト用の保存エラー'}}
        if method == 'GET':
            return {'status': 200, 'body': {'memos': self.memos}}
        if method == 'DELETE':
            self.memos = [m for m in self.memos if m['id'] != path.rsplit('/', 1)[-1]]
            return {'status': 200, 'body': {'ok': True}}
        memo_id = path.rsplit('/', 1)[-1] if method == 'PUT' else f'new-{len(self.calls)}'
        saved = {**body, 'id': memo_id, 'createdAt': TIME, 'updatedAt': TIME}
        self.memos = [m for m in self.memos if m['id'] != memo_id] + [saved]
        return {'status': 200, 'body': saved}

    def route(self, route):
        req = route.request
        result = self.api(req.url, req.method, req.post_data_json)
        route.fulfill(status=result['status'], json=result['body'])


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_args):
        pass


def boot(page, fixture, url, offline):
    if not offline:
        page.route('**/api/**', fixture.route)
        page.goto(url, wait_until='networkidle')
    else:
        # Same sources, but skip URL navigation and native module resolution in managed Chromium.
        html = (READER / 'index.html').read_text()
        html = re.sub(r'<script[^>]*>.*?</script>|<link[^>]*>', '', html, flags=re.S)
        html = html.replace('</head>', '<style>' + (READER / 'app.css').read_text()
                            + (READER / 'memo.css').read_text() + '</style></head>')
        page.set_content(html)
        page.expose_function('__memoFixture', fixture.api)
        page.evaluate('''data => { window.fetch = async (url, opt = {}) => {
          const result = String(url).startsWith('/api/')
            ? await window.__memoFixture(String(url), opt.method || 'GET', opt.body ? JSON.parse(opt.body) : null)
            : {status: 200, body: data};
          return new Response(JSON.stringify(result.body), {status: result.status, headers: {'Content-Type':'application/json'}});
        }; }''', json.loads((READER / f'data/{PART}.json').read_text()))
        page.add_script_tag(content=(READER / 'app.js').read_text())
        source = (READER / 'memo-model.mjs').read_text().replace('export function', 'function')
        source += '\n' + re.sub(r'^import .*?;\n', '', (READER / 'memo.js').read_text(), flags=re.M)
        page.add_script_tag(content=source)
        page.add_script_tag(content=(READER / 'trombone3d-addon.js').read_text())
    page.wait_for_function('window.__dynamic !== undefined')
    if fixture.enabled:
        page.wait_for_function("!document.getElementById('memoSettings').hidden")


def open_bar(page, label='59', pointer=False, touch=False):
    target = page.locator(f'#sys-3 .bar-target[data-seg="{label}"]')
    if pointer:
        target.evaluate("el => el.scrollIntoView({block:'center',inline:'center'})")
        page.evaluate('''() => { const t=document.querySelector('#sys-3').getBoundingClientRect();
          const h=document.getElementById('bar').getBoundingClientRect().bottom;
          if(t.top < h + 30) window.scrollBy(0, t.top-h-30); }''')
        box = target.bounding_box()
        position = {'x': box['width'] / 2, 'y': 5}
        (target.tap if touch else target.click)(position=position)
    else:
        target.focus()
        page.keyboard.press('Enter')
    expect(page.locator('#ctx')).to_be_visible()


def action(page, text):
    page.locator('#ctx').get_by_role('menuitem', name=text, exact=True).click()


def assert_geometry(page):
    result = page.locator('#sys-3').evaluate('''el => {
      const svg = el.querySelector('svg').getBoundingClientRect();
      const band = el.querySelector('.memo-band').getBoundingClientRect();
      const cards = [...el.querySelectorAll('.memo-card')].map(c => c.getBoundingClientRect());
      const bar = el.querySelector('.bar-target[data-seg="59"]').getBoundingClientRect();
      return {below: band.top >= svg.bottom-1, width: Math.abs(band.width-svg.width)<1,
        aligned: cards.every(c => c.left>=bar.left-1 && c.right<=bar.right+1),
        stacked: cards.every((c,i)=>!i || c.top>=cards[i-1].bottom)};
    }''')
    assert all(result.values()), result


def exercise(page, fixture, out, name, offline, touch):
    expect(page.locator('#memoPen,#memoReh,#rehList,.memo-pin')).to_have_count(0)
    expect(page.locator('.toplinks #memoListBtn,.now #memoStatus')).to_have_count(0)
    expect(page.locator('#sys-3 .memo-card[data-memo="legacy"]')).to_have_count(1)
    expect(page.locator('.memo-card[data-memo="unknown"]')).to_have_count(0)
    assert_geometry(page)
    compact = page.viewport_size['width'] <= 1024
    if compact:
        toolbar_box = page.locator('#bar').bounding_box()
        assert toolbar_box['height'] <= 90, f"compact toolbar too tall: {toolbar_box}"
        assert page.locator('#readerExtras').evaluate("el => el.parentElement.id") == 'compactExtrasMount'
        expect(page.locator('#settings')).not_to_be_visible()
    # Actual mouse/touch click on the bar, not a pen/toolbar or arbitrary-coordinate editor.
    open_bar(page, pointer=True, touch=touch)
    # A focus-generated scroll event already queued at the current position
    # must not dismiss a keyboard menu. A subsequent actual scroll still must.
    page.evaluate("window.dispatchEvent(new Event('scroll'))")
    expect(page.locator('#ctx')).to_be_visible()
    expect(page.locator('#ctx')).not_to_contain_text('練習記号')
    box = page.locator('#ctx').bounding_box()
    vp = page.viewport_size
    assert box['x'] >= 0 and box['x'] + box['width'] <= vp['width'] + 1
    assert box['y'] >= 0 and box['y'] + box['height'] <= vp['height'] + 1
    buttons = page.locator('#ctx button').evaluate_all('els=>els.map(e=>e.getBoundingClientRect().top)')
    assert all(a < b for a, b in zip(buttons, buttons[1:])), 'menu must be vertical'
    page.screenshot(path=str(out / f'{name}-menu.png'))
    action(page, 'この59小節目にメモを追加')
    expect(page.locator('#memoTitle')).to_have_text('この59小節目にメモを追加')
    expect(page.locator('#memoText')).to_be_focused()
    page.locator('#memoText').fill('前の小節で息を吸う。' * 8 + '<img src=x onerror=alert(1)>')
    page.locator('[name=memoKind][value=good]').check()
    page.screenshot(path=str(out / f'{name}-editor.png'))
    scroll_before = page.locator('#sys-3 .sc').evaluate('el => el.scrollLeft')
    page.locator('#memoSave').click()
    expect(page.locator('#memo')).not_to_be_visible()
    assert abs(page.locator('#sys-3 .sc').evaluate('el => el.scrollLeft') - scroll_before) < 1
    write = next(c for c in reversed(fixture.calls) if c['method'] == 'POST')
    assert set(write['body']) == {'text', 'kind', 'anchor'}, write
    assert write['body']['anchor'] == {'mvt': 'I', 'bar': 59}
    assert write['body']['kind'] == 'good'
    expect(page.locator('#sys-3 .memo-card')).to_have_count(2)
    expect(page.locator('.memo-card img')).to_have_count(0)
    assert_geometry(page)
    page.locator('#sys-3 .memo-band').scroll_into_view_if_needed()
    page.screenshot(path=str(out / f'{name}-saved.png'))
    # Zoom/reflow/bar-number visibility never change bar identity or cover notation.
    opened_settings = False
    if not page.locator('[data-bar-pos=top]').is_visible():
        page.locator('#setBtn').click()
        expect(page.locator('#settings')).to_be_visible()
        opened_settings = True
        if compact:
            settings_box = page.locator('#settings').bounding_box()
            assert settings_box['y'] >= -1, settings_box
            assert settings_box['y'] + settings_box['height'] <= page.viewport_size['height'] + 1, settings_box
            assert settings_box['height'] <= page.viewport_size['height'] * .76, settings_box
            page.screenshot(path=str(out / f'{name}-settings.png'))
    for pos in ['top', 'off', 'bottom']:
        page.locator(f'[data-bar-pos={pos}]').click()
        assert_geometry(page)
    page.locator('#zoomIn').click()
    assert_geometry(page)
    page.locator('#zoomOut').click()
    if opened_settings:
        page.locator('#setBtn').click()
        expect(page.locator('#settings')).not_to_be_visible()
    # Existing legacy metadata is not exposed or silently destroyed by editing text.
    page.locator('[data-memo=legacy]').click()
    page.locator('#memoText').fill('更新したメモ')
    page.locator('#memoSave').click()
    expect(page.locator('#memo')).not_to_be_visible()
    assert fixture.memos[-1]['rehearsal'] == 'H'
    assert fixture.memos[-1]['anchor'] == {'mvt': 'I', 'bar': 59}
    # Keyboard entry and a measure inside a multi-measure rest.
    open_bar(page, '61–76')
    number = page.get_by_label('休みの中の小節番号')
    for bad in ['60', '77', '65.5', '']:
        number.fill(bad)
        expect(page.locator('#ctx .ctx-score')).to_be_disabled()
        assert 'メモを追加' not in page.locator('#ctx').inner_text()
    number.fill('65')
    action(page, 'この65小節目にメモを追加')
    page.locator('#memoText').fill('65小節目から数え直す')
    page.locator('#memoSave').click()
    expect(page.locator('#memo')).not_to_be_visible()
    assert fixture.memos[-1]['anchor'] == {'mvt': 'I', 'bar': 65}
    # Failed saves keep the draft and permit retry; delete confirms and removes only one id.
    open_bar(page)
    action(page, 'この59小節目にメモを追加')
    page.locator('#memoText').fill('消えない下書き')
    fixture.fail = 500
    page.locator('#memoSave').click()
    expect(page.locator('#memoErr')).to_be_visible()
    expect(page.locator('#memoText')).to_have_value('消えない下書き')
    page.locator('#memoSave').click()
    expect(page.locator('#memo')).not_to_be_visible()
    last_id = fixture.memos[-1]['id']
    page.locator(f'[data-memo="{last_id}"]').click()
    page.once('dialog', lambda d: d.accept())
    page.locator('#memoDelete').click()
    expect(page.locator('#memo')).not_to_be_visible()
    expect(page.locator(f'[data-memo="{last_id}"]')).to_have_count(0)
    # Unknown anchors are retained in the list, never guessed at old screen coordinates.
    open_bar(page)
    action(page, '練習メモ一覧')
    expect(page.locator('#memoList')).to_contain_text('位置不明')
    expect(page.locator('[data-go=unknown]')).to_be_disabled()
    page.locator('#memoList form > button').click()
    # Note playback and the long-tone gesture still belong to the reader.
    note = page.locator('#sys-3 .note').first
    note_id = int(note.get_attribute('data-id'))
    note.locator('.hit').last.click()
    assert page.evaluate('window.__dynamic.cur') == note_id
    expect(page.locator('#ctx')).not_to_be_visible()
    note.locator('.hit').last.dblclick()
    expect(page.locator('#practice')).to_be_visible()
    page.locator('#practice button[type=submit]').click()
    note.locator('.hit').last.click(button='right')
    expect(page.locator('#practice')).to_be_visible()
    page.locator('#practice button[type=submit]').click()
    # Expired identity removes personal display and keeps an unsaved draft visible.
    open_bar(page)
    action(page, 'この59小節目にメモを追加')
    page.locator('#memoText').fill('セッション期限切れの下書き')
    fixture.fail = 401
    page.locator('#memoSave').click()
    expect(page.locator('#memoErr')).to_be_visible()
    expect(page.locator('.memo-card')).to_have_count(0)
    page.locator('#memoCancel').click()
    open_bar(page)
    action(page, 'この59小節目にメモを追加')
    expect(page.locator('#memoLoginPrompt')).to_be_visible()
    page.locator('#memoLoginPrompt button[type=submit]').click()
    return {'viewport': name, 'result': 'PASS', 'api_writes': len([c for c in fixture.calls if c['method'] != 'GET'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser')
    parser.add_argument('--offline', action='store_true')
    parser.add_argument('--out', type=Path, default=Path('/tmp/dynamic-memo-evidence'))
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT / 'public')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/reader/?part={PART}'
    results = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(**({'executable_path': args.browser} if args.browser else {}), args=['--no-sandbox'])
            for name, width, height, touch in [('desktop', 1440, 1000, False), ('tablet', 820, 1180, True), ('mobile', 390, 844, True)]:
                context = browser.new_context(viewport={'width': width, 'height': height}, has_touch=touch, is_mobile=touch, reduced_motion='reduce', service_workers='block')
                page = context.new_page(); page.set_default_timeout(8000)
                errors, requests = [], []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.on('request', lambda r: requests.append(r.url))
                fixture = Fixture('dvorak8-horn2' if args.offline else PART)
                try:
                    boot(page, fixture, url, args.offline)
                    results.append(exercise(page, fixture, args.out, name, args.offline, touch))
                    assert not any('/score/' in u or 'score-viewer.js' in u or '/vendor/three' in u for u in requests), requests
                    assert not errors, errors
                    print(name, 'PASS', flush=True)
                except Exception:
                    page.screenshot(path=str(args.out / f'{name}-failure.png'))
                    (args.out / 'errors.json').write_text(json.dumps(errors, ensure_ascii=False))
                    raise
                finally:
                    context.close()
            # Only real URL loading can verify module imports, navigation and print guards.
            if not args.offline:
                for mode in ['disabled', 'unsupported', 'print', 'resume']:
                    context = browser.new_context(service_workers='block')
                    page = context.new_page(); fixture = Fixture()
                    if mode == 'disabled': fixture.enabled = False
                    if mode == 'unsupported': fixture.part = 'different-part'
                    if mode == 'resume':
                        page.add_init_script("sessionStorage.setItem('dynamic-memo-intent', JSON.stringify({part:'dvorak8-trombone1',anchor:{mvt:'I',bar:65}}))")
                    page.route('**/api/**', fixture.route)
                    page.goto(url + ('&print=1' if mode == 'print' else ''), wait_until='networkidle')
                    page.wait_for_function('window.__dynamic !== undefined')
                    if mode == 'resume':
                        expect(page.locator('#memoTitle')).to_have_text('この65小節目にメモを追加')
                        expect(page.locator('#memo')).to_be_visible()
                        assert page.evaluate("sessionStorage.getItem('dynamic-memo-intent')") is None
                    else:
                        expect(page.locator('#memoSettings')).to_be_hidden()
                        expect(page.locator('.memo-card')).to_have_count(0)
                        if mode == 'print': assert not fixture.calls
                        else:
                            open_bar(page)
                            assert 'メモを追加' not in page.locator('#ctx').inner_text()
                    results.append({'scenario': mode, 'result': 'PASS'}); context.close()
                # Existing full-score action retains its exact selected movement/bar, lazy loader intact.
                context = browser.new_context(service_workers='block'); page = context.new_page(); fixture = Fixture()
                page.set_default_timeout(8000)
                boot(page, fixture, url, False)
                page.route('**/score-viewer.js', lambda r: r.fulfill(content_type='text/javascript', body='window.DynamicScore={open:async arg=>{window.__scoreTarget=arg}};'))
                open_bar(page, '61–76'); page.get_by_label('休みの中の小節番号').fill('65')
                action(page, '65小節目のスコアを見る')
                page.wait_for_function('window.__scoreTarget !== undefined')
                assert page.evaluate('window.__scoreTarget.bar') == 65
                assert page.evaluate('window.__scoreTarget.mvt') == 'I'
                results.append({'scenario': 'lazy-score-target', 'result': 'PASS'})
                open_bar(page)
                page.evaluate("window.scrollBy(0, 20)")
                expect(page.locator('#ctx')).not_to_be_visible()
                results.append({'scenario': 'menu-scroll-dismissal', 'result': 'PASS'}); context.close()
            report = {'mode': 'inline-offline' if args.offline else 'served-native-modules', 'browser': browser.version, 'results': results,
                      'limitations': 'Synthetic API; no live Google/Access/R2 writes. Offline harness does not verify native module loading or navigation.' if args.offline else 'Synthetic API; no live Google/Access/R2 writes. Full-score target contract is stubbed.'}
            (args.out / 'results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
            browser.close()
    finally:
        server.shutdown(); server.server_close()


if __name__ == '__main__':
    main()
