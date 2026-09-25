/* DYNAMIC 総譜ビューア — loaded on demand; nothing is fetched until a viewer is opened. */
(() => {
  'use strict';
  const MV_NUM = { I: 1, II: 2, III: 3, IV: 4 };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  let catalog = null;                    // Promise of score/index.json
  const scores = new Map();              // id -> Promise of index data
  let V = null;                          // viewer state

  function base() { return new URL('../', document.currentScript?.src || location.href); }
  const ROOT = base();

  function getCatalog() {
    if (!catalog) catalog = fetch(new URL('score/index.json', ROOT)).then((r) => (r.ok ? r.json() : { scores: [] })).catch(() => ({ scores: [] }));
    return catalog;
  }
  async function findScore(work, composer) {
    const c = await getCatalog();
    return c.scores.find((s) => s.work === work && (!composer || s.composer === composer)) || null;
  }
  function loadScore(entry) {
    if (!scores.has(entry.id)) {
      scores.set(entry.id, fetch(new URL(entry.index, ROOT)).then((r) => {
        if (!r.ok) throw new Error(`総譜データを読み込めませんでした（${r.status}）`);
        return r.json();
      }).then((d) => {
        d.base = new URL(entry.index, ROOT);
        d.where = new Map();            // "I:5" -> [page, system, bar]
        d.pages.forEach((p, pi) => p.systems.forEach((s, si) => s.bars.forEach((b, bi) => d.where.set(`${p.mvt}:${b[2]}`, [pi, si, bi]))));
        return d;
      }));
      scores.get(entry.id).catch(() => scores.delete(entry.id));
    }
    return scores.get(entry.id);
  }

  // ---------- DOM ----------
  function build() {
    const dlg = document.createElement('dialog');
    dlg.className = 'scorev';
    dlg.setAttribute('aria-label', '総譜');
    dlg.innerHTML = `
      <header class="sv-top">
        <div class="sv-ttl"><b class="sv-name">総譜</b><span class="sv-where" aria-live="polite"></span></div>
        <div class="sv-nav">
          <button type="button" class="sv-prev" aria-label="前のページ" title="前のページ（←）">‹ 前</button>
          <span class="sv-pg"></span>
          <button type="button" class="sv-next" aria-label="次のページ" title="次のページ（→）">次 ›</button>
        </div>
        <form class="sv-jump"><select class="sv-mvt" aria-label="楽章"></select><input class="sv-bar" type="number" inputmode="numeric" min="1" placeholder="小節" aria-label="小節番号"><button>移動</button></form>
        <div class="sv-tools">
          <button type="button" class="sv-fit" title="幅に合わせる／ページ全体">全体</button>
          <button type="button" class="sv-close" aria-label="閉じる" title="閉じる（Esc）">✕</button>
        </div>
      </header>
      <div class="sv-stage" tabindex="-1"><div class="sv-page"><img alt="" decoding="async"><svg class="sv-ov" aria-hidden="true"></svg></div><div class="sv-page" hidden><img alt="" decoding="async"><svg class="sv-ov" aria-hidden="true"></svg></div><p class="sv-msg" hidden></p></div>
      <footer class="sv-foot"></footer>`;
    document.body.appendChild(dlg);
    const $ = (s) => dlg.querySelector(s);
    const st = { dlg, $, stage: $('.sv-stage'), msg: $('.sv-msg'), pgs: [] };
    dlg.querySelectorAll('.sv-page').forEach((root) => {
      st.pgs.push({ root, img: root.querySelector('img'), ov: root.querySelector('.sv-ov') });
    });
    $('.sv-close').onclick = () => dlg.close();
    $('.sv-prev').onclick = () => turnPage(-1);
    $('.sv-next').onclick = () => turnPage(+1);
    $('.sv-fit').onclick = () => { V.fit = V.fit === 'page' ? 'width' : 'page'; try { localStorage.setItem('dynamic-score-fit', V.fit); } catch (e) { /* ignore */ } layout(); };
    $('.sv-jump').onsubmit = (e) => {
      e.preventDefault();
      const bar = parseInt($('.sv-bar').value, 10); if (!bar) return;
      const w = V.d.where.get(`${$('.sv-mvt').value}:${bar}`);
      if (w) show(w[0], { mvt: $('.sv-mvt').value, bar }); else note(`${bar}小節は見つかりませんでした。`);
    };
    dlg.addEventListener('keydown', (e) => {
      if (e.target.matches('input,select')) return;
      if (e.key === 'ArrowRight' || e.key === 'PageDown') { e.preventDefault(); turnPage(+1); }
      else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { e.preventDefault(); turnPage(-1); }
    });
    dlg.addEventListener('close', () => { document.documentElement.classList.remove('sv-open'); V.onclose?.(); });
    // swipe left / right to turn pages (only when the page is not horizontally scrollable)
    let sx = null, sy = 0;
    st.stage.addEventListener('pointerdown', (e) => { if (e.pointerType !== 'mouse') { sx = e.clientX; sy = e.clientY; } });
    st.stage.addEventListener('pointerup', (e) => {
      if (sx == null) return; const dx = e.clientX - sx, dy = e.clientY - sy; sx = null;
      if (st.stage.scrollWidth > st.stage.clientWidth + 4) return;
      if (Math.abs(dx) > 70 && Math.abs(dy) < 50) turnPage(dx < 0 ? 1 : -1);
    });
    st.pgs.forEach((pg) => {
      pg.img.addEventListener('load', () => { st.msg.hidden = true; pg.root.classList.remove('loading'); layout(); scrollToTarget(); prefetch(); });
      pg.img.addEventListener('error', () => { pg.root.classList.remove('loading'); note('画像を読み込めませんでした。通信状況を確認してください。'); });
    });
    new ResizeObserver(() => V && V.d && layout()).observe(st.stage);
    return st;
  }
  function note(t) { V.st.msg.textContent = t; V.st.msg.hidden = false; }

  // Book spread pairing on 0-indexed pages: page 0 alone, then (1,2), (3,4), …
  // so even printed pages sit on the left and odd on the right.
  function pairOf(pi) {
    if (pi === 0) return [0, -1];
    const L = pi % 2 ? pi : pi - 1;
    return [L, L + 1];
  }
  function visibleIdx() { return V.spread ? pairOf(V.pi) : [V.pi, -1]; }
  function pageWidth(k) {
    const q = V.d.pages[k], stage = V.st.stage;
    return Math.min(stage.clientWidth, (stage.clientHeight - 8) * q.w / q.h);
  }
  function layout() {
    const { stage } = V.st;
    const byH = V.fit === 'page';
    const [L, R] = pairOf(V.pi);
    const spread = byH && R >= 0 && R < V.d.pages.length
      && pageWidth(L) + pageWidth(R) + 12 <= stage.clientWidth;
    if (spread !== V.spread) { V.spread = spread; syncImgs(); overlay(); where(); }
    stage.classList.toggle('spread', !!spread);
    V.st.pgs.forEach((pg, i) => {
      const k = visibleIdx()[i];
      if (k == null || k < 0 || !V.d.pages[k]) { pg.root.hidden = true; return; }
      pg.root.hidden = false;
      const q = V.d.pages[k];
      const w = byH ? pageWidth(k) : stage.clientWidth;
      pg.root.style.width = `${Math.max(200, w)}px`;
      pg.img.width = q.w; pg.img.height = q.h;
    });
    V.st.$('.sv-fit').textContent = byH ? '幅に合わせる' : 'ページ全体';
  }
  function overlay() {
    V.st.pgs.forEach((pg, i) => {
      const k = visibleIdx()[i];
      if (k == null || k < 0 || !V.d.pages[k]) return;
      const p = V.d.pages[k], o = [];
      o.push(`<svg viewBox="0 0 ${p.w} ${p.h}">`);
      const fs = Math.max(18, Math.round(p.w / 64));
      p.systems.forEach((s) => {
        for (const [x0, x1, bar] of s.bars) {
          const on = V.target && V.target.mvt === p.mvt && V.target.bar === bar;
          o.push(`<rect class="sv-hit${on ? ' on' : ''}" data-mvt="${p.mvt}" data-bar="${bar}" x="${x0}" y="${s.y0}" width="${x1 - x0}" height="${s.y1 - s.y0}"/>`);
          const tw = fs * (String(bar).length * 0.62 + 0.5);
          o.push(`<g class="sv-num${on ? ' on' : ''}"><rect x="${x0 + 2}" y="${s.y0 - fs - 6}" width="${tw}" height="${fs + 4}" rx="4"/><text x="${x0 + 2 + tw / 2}" y="${s.y0 - 8}" font-size="${fs}">${bar}</text></g>`);
        }
      });
      o.push('</svg>');
      pg.ov.outerHTML = o.join('').replace('<svg ', '<svg class="sv-ov" aria-hidden="true" ');
      pg.ov = pg.root.querySelector('.sv-ov');
      pg.ov.addEventListener('click', (e) => {
        const r = e.target.closest('[data-bar]'); if (!r) return;
        V.target = { mvt: r.dataset.mvt, bar: +r.dataset.bar }; overlay(); where();
      });
    });
  }
  function where() {
    const p = V.d.pages[V.pi], { $ } = V.st;
    const bars = p.systems.flatMap((s) => s.bars.map((b) => b[2]));
    const mv = `${MV_NUM[p.mvt] || p.mvt}楽章`;
    $('.sv-where').textContent = V.target && V.target.mvt === p.mvt && bars.includes(V.target.bar)
      ? `${mv} ${V.target.bar}小節` : `${mv} ${bars[0]}〜${bars[bars.length - 1]}小節`;
    if (V.spread) {
      const [L, R] = pairOf(V.pi);
      $('.sv-pg').textContent = `p.${V.d.pages[L].printed}–${V.d.pages[R].printed}（${L + 1}–${R + 1}/${V.d.pages.length}）`;
      $('.sv-prev').disabled = L <= 0; $('.sv-next').disabled = R >= V.d.pages.length - 1;
    } else {
      $('.sv-pg').textContent = `p.${p.printed}（${V.pi + 1}/${V.d.pages.length}）`;
      $('.sv-prev').disabled = V.pi <= 0; $('.sv-next').disabled = V.pi >= V.d.pages.length - 1;
    }
    $('.sv-mvt').value = p.mvt;
  }
  function scrollToTarget() {
    const p = V.d.pages[V.pi], { stage } = V.st;
    const slot = V.st.pgs[Math.max(0, visibleIdx().indexOf(V.pi))];
    let y = 0;
    if (V.target && V.target.mvt === p.mvt) {
      const s = p.systems.find((q) => q.bars.some((b) => b[2] === V.target.bar));
      if (s) y = s.y0 / p.h * slot.root.clientHeight - 40;
    }
    stage.scrollTo({ top: Math.max(0, y), left: 0 });
  }
  function prefetch() {                  // neighbours only, and only while the viewer is open
    const ks = V.spread ? [pairOf(V.pi)[0] - 1, pairOf(V.pi)[1] + 1] : [V.pi + 1, V.pi - 1];
    for (const k of ks) {
      const p = V.d.pages[k]; if (!p || V.pre.has(k)) continue;
      V.pre.add(k); const im = new Image(); im.decoding = 'async'; im.src = new URL(p.img, V.d.base).href;
    }
  }
  // Assign each visible page element its image (or hide it when out of range).
  function syncImgs() {
    V.st.pgs.forEach((pg, i) => {
      const k = visibleIdx()[i];
      if (k == null || k < 0 || !V.d.pages[k]) { pg.root.hidden = true; pg.img.removeAttribute('src'); return; }
      pg.root.hidden = false;
      const src = new URL(V.d.pages[k].img, V.d.base).href;
      if (pg.img.src !== src) {
        pg.root.classList.add('loading');
        pg.img.removeAttribute('src');
        pg.img.src = src;
      } else if (!pg.img.complete) {
        pg.root.classList.add('loading');
      } else if (pg.img.naturalWidth > 0) {
        pg.root.classList.remove('loading');
      } else {
        pg.root.classList.remove('loading');
        note('画像を読み込めませんでした。通信状況を確認してください。');
      }
    });
  }
  function show(pi, target) {
    if (!V.d.pages[pi]) return;
    V.pi = pi; if (target !== undefined) V.target = target;
    V.st.msg.hidden = true;
    syncImgs();
    layout(); scrollToTarget();
    overlay(); where();
    V.st.stage.focus({ preventScroll: true });
  }
  function go(pi) { if (V && V.d.pages[pi]) show(pi); }
  // In spread mode a "turn" moves a whole leaf; otherwise one page.
  function turnPage(dir) {
    if (!V || !V.d) return;
    if (V.spread) {
      const [L, R] = pairOf(V.pi);
      const next = dir > 0 ? (R < 0 ? L + 1 : R + 1) : Math.max(0, L - 1);
      go(next);
    } else go(V.pi + dir);
  }

  /**
   * Open the score of `work` at movement `mvt`, bar `bar`.
   * opts: { work, composer, mvt, bar, onclose }
   */
  async function open(opts) {
    const entry = await findScore(opts.work, opts.composer);
    if (!entry) throw new Error('この曲の総譜はまだありません。');
    if (!V) {
      let fit = innerWidth > innerHeight ? 'page' : 'width';
      try { fit = localStorage.getItem('dynamic-score-fit') || fit; } catch (e) { /* ignore */ }
      V = { st: build(), fit, pre: new Set() };
    }
    V.onclose = opts.onclose;
    const { dlg, $, pgs } = V.st;
    if (!dlg.open) { dlg.showModal(); document.documentElement.classList.add('sv-open'); }
    pgs.forEach((pg) => pg.root.classList.add('loading')); V.st.msg.hidden = true;
    let d;
    try { d = await loadScore(entry); } catch (e) { note(e.message); pgs.forEach((pg) => pg.root.classList.remove('loading')); return; }
    if (V.d !== d) {
      V.d = d; V.pre = new Set();
      $('.sv-name').textContent = d.title;
      $('.sv-mvt').innerHTML = d.movements.map((m) => `<option value="${m.key}">${MV_NUM[m.key] || m.key}楽章</option>`).join('');
      $('.sv-foot').innerHTML = `${esc(d.edition)} · ${esc(d.status)} <span class="sv-lim">${d.limitations.map(esc).join(' ')}</span>`;
    }
    const w = d.where.get(`${opts.mvt}:${opts.bar}`);
    if (w) show(w[0], { mvt: opts.mvt, bar: opts.bar });
    else {
      const first = d.pages.findIndex((p) => p.mvt === opts.mvt);
      show(first < 0 ? 0 : first, null);
      if (opts.bar) note(`${opts.bar}小節は総譜で見つかりませんでした。`);
    }
  }

  window.DynamicScore = { open, has: async (work, composer) => !!(await findScore(work, composer)) };
})();
