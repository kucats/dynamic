/* DYNAMIC score selection — public landing page */
(() => {
  'use strict';

  const main = document.querySelector('main.wrap');
  if (!main) return;

  const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
  const publicPath = (value) => {
    const path = String(value || '');
    if (!path.startsWith('public/')) return '';
    return path.slice('public/'.length).split('/').map(encodeURIComponent).join('/');
  };
  const composerLabel = (composer) => ({
    'Antonín Dvořák': 'ドヴォルザーク',
    'Giuseppe Verdi': 'ヴェルディ'
  })[composer] || composer;
  const workLabel = (work) => ({
    'Symphony No. 8 in G major, Op. 88': '交響曲第8番',
    'Symphony No. 8, Op. 88': '交響曲第8番',
    'Nabucco — Sinfonia': '歌劇《ナブッコ》序曲'
  })[work] || work;

  const selector = document.createElement('section');
  selector.id = 'dynamicSelector';
  selector.setAttribute('aria-labelledby', 'selectorTitle');
  selector.innerHTML = `
    <div class="ds-intro">
      <p class="ds-eyebrow">DYNAMIC SCORE READER</p>
      <h1 id="selectorTitle">譜読みする曲を選ぶ</h1>
      <p>パートからでも、作曲家からでも探せます。資料の確認状況を見て、開く譜面を選べます。</p>
    </div>
    <div class="ds-routes" aria-label="選曲方法">
      <button class="ds-route ds-route-primary" type="button" data-route="instrument">
        <span class="ds-route-art"><img src="assets/instrument-horn.png" alt=""><img src="assets/instrument-trombone.png" alt=""></span>
        <span class="ds-route-copy"><span class="ds-route-kicker">PART FIRST</span><strong>パートから選ぶ</strong><span class="ds-route-description">ホルン、トロンボーンなど<br>吹く楽器から探す</span></span>
        <span class="ds-route-arrow" aria-hidden="true">›</span>
      </button>
      <button class="ds-route" type="button" data-route="composer">
        <span class="ds-composer-art" aria-hidden="true"><span class="ds-composer-mark"><span>D</span><i>♪</i><span>V</span></span></span>
        <span class="ds-route-copy"><span class="ds-route-kicker">COMPOSER FIRST</span><strong>作曲家から選ぶ</strong><span class="ds-route-description">曲を先に決めて<br>譜読みするパートを探す</span></span>
        <span class="ds-route-arrow" aria-hidden="true">›</span>
      </button>
    </div>
    <p class="ds-counts" id="selectorCounts" aria-live="polite">譜読み資料を読み込んでいます…</p>
    <section class="ds-browser" id="scoreBrowser" aria-live="polite" hidden>
      <div class="ds-browser-head">
        <button class="ds-back" type="button">‹ 戻る</button>
        <div class="ds-browser-heading"><p class="ds-eyebrow" id="browserEyebrow"></p><h2 id="browserTitle"></h2><p class="ds-browser-lede" id="browserLede"></p></div>
        <button class="ds-home-button" type="button">選び直す</button>
      </div>
      <div id="browserContent"></div>
    </section>
    <aside class="ds-helper"><strong>譜面の確認状況</strong><br>資料ごとに確認の進み具合が違います。独立監査前の譜面や下書きには、その状態と注意点を表示しています。</aside>`;

  const oldHeading = main.querySelector('h2');
  if (oldHeading) oldHeading.textContent = 'すぐに開く';
  main.insertBefore(selector, main.firstChild);

  const browser = selector.querySelector('#scoreBrowser');
  const content = selector.querySelector('#browserContent');
  const browserTitle = selector.querySelector('#browserTitle');
  const browserEyebrow = selector.querySelector('#browserEyebrow');
  const browserLede = selector.querySelector('#browserLede');
  const counts = selector.querySelector('#selectorCounts');
  let records = [];
  let currentRoute = '';
  let currentFacet = null;
  let step = 'home';

  function showBrowser(title, eyebrow, lede, html) {
    browserTitle.textContent = title;
    browserEyebrow.textContent = eyebrow;
    browserLede.textContent = lede;
    content.innerHTML = html;
    browser.hidden = false;
    step = 'results';
    browser.scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
  }

  function recordPartLabel(record) {
    if (record.reader) {
      const match = record.title.match(/ホルン[0-9一二三四]+番/);
      return match ? match[0] : record.title;
    }
    return record.instrument.replace(/\s*[—·].*$/, '').replace(/ in [A-G]$/, '');
  }

  function familyOf(record) {
    return /horn|corno|ホルン/i.test(`${record.instrument} ${record.title}`) ? 'horn' : 'trombone';
  }

  function routeFacets(route) {
    const seen = new Map();
    for (const record of records) {
      const key = route === 'instrument' ? familyOf(record) : record.composerKey;
      if (!key) continue;
      if (!seen.has(key)) seen.set(key, []);
      seen.get(key).push(record);
    }
    if (route === 'instrument') {
      return ['horn', 'trombone'].filter((key) => seen.has(key)).map((key) => ({ key, records: seen.get(key) }));
    }
    return [...seen.entries()].map(([key, items]) => ({ key, records: items })).sort((a, b) => a.key.localeCompare(b.key));
  }

  function renderFacets(route) {
    currentRoute = route;
    currentFacet = null;
    const facets = routeFacets(route);
    const html = `<div class="ds-facets">${facets.map(({ key, records: matches }) => {
      if (route === 'instrument') {
        const horn = key === 'horn';
        const title = horn ? 'ホルン' : 'トロンボーン';
        const image = horn ? 'assets/instrument-horn.png' : 'assets/instrument-trombone.png';
        const sub = horn ? 'Horn · Corno' : 'Trombone';
        return `<button type="button" class="ds-facet" data-facet="${esc(key)}"><img src="${image}" alt="" loading="lazy" decoding="async"><span class="ds-facet-copy"><strong>${title}</strong><small>${sub} · ${matches.length}件の資料</small></span><span class="ds-facet-arrow" aria-hidden="true">›</span></button>`;
      }
      const label = composerLabel(matches[0].composer);
      const initial = key === 'antonin-dvorak' ? 'D' : key === 'giuseppe-verdi' ? 'V' : label.slice(0, 1);
      const line = matches.length === 1 ? '1件の資料' : `${matches.length}件の資料`;
      return `<button type="button" class="ds-facet" data-facet="${esc(key)}"><span class="ds-facet-letters" aria-hidden="true">${esc(initial)}</span><span class="ds-facet-copy"><strong>${esc(label)}</strong><small>${esc(matches[0].composer)} · ${line}</small></span><span class="ds-facet-arrow" aria-hidden="true">›</span></button>`;
    }).join('')}</div>`;
    showBrowser(route === 'instrument' ? '楽器・パートを選ぶ' : '作曲家を選ぶ', 'STEP 1',
      route === 'instrument' ? '楽器を選ぶと、曲とパートの一覧が表示されます。' : '作曲家を選ぶと、公開中の曲とパートが表示されます。', html);
    step = 'facets';
  }

  function statusMarkup(record) {
    const klass = record.reviewed ? ' ds-status-reviewed' : ' ds-status-draft';
    return `<span class="ds-status${klass}">${esc(record.reviewStatus)}</span>`;
  }

  function linksMarkup(record) {
    const links = [];
    if (record.open) links.push(`<a class="ds-primary-link" href="${esc(record.open)}">${record.reader ? '譜面を開く' : 'ガイドを見る'}</a>`);
    for (const link of record.links) links.push(`<a class="ds-secondary-link" href="${esc(link.href)}">${esc(link.label)}</a>`);
    return links.length ? `<div class="ds-card-actions">${links.join('')}</div>` : '';
  }

  function cardMarkup(record) {
    const details = record.limitations?.length
      ? `<details class="ds-card-more"><summary>内容と確認上の注意</summary><ul>${record.limitations.map((item) => `<li>${esc(item)}</li>`).join('')}</ul></details>` : '';
    return `<article class="ds-part-card"><h4>${esc(recordPartLabel(record))}</h4>${statusMarkup(record)}<p class="ds-part-meta">${esc(record.summary)}</p>${linksMarkup(record)}${details}</article>`;
  }

  function workGroups(matches) {
    const groups = new Map();
    for (const record of matches) {
      const key = `${record.composerKey || record.composer}::${record.work}`;
      if (!groups.has(key)) groups.set(key, { composer: record.composer, work: record.work, records: [] });
      groups.get(key).records.push(record);
    }
    return [...groups.values()].sort((a, b) => a.composer.localeCompare(b.composer) || a.work.localeCompare(b.work));
  }

  function renderResults(route, facetKey) {
    currentRoute = route;
    currentFacet = facetKey;
    const matches = records.filter((record) => route === 'instrument'
      ? familyOf(record) === facetKey
      : record.composerKey === facetKey);
    const groups = workGroups(matches);
    const heading = route === 'instrument'
      ? (facetKey === 'horn' ? 'ホルン' : 'トロンボーン')
      : composerLabel(matches[0]?.composer || '作曲家');
    const html = `<div class="ds-results-top"><input class="ds-search" type="search" aria-label="曲名・パート名で検索" placeholder="曲名・パート名で検索"><button class="ds-search-clear" type="button">検索を消す</button></div><div class="ds-work-list">${groups.map((group) => `
      <section class="ds-work-section"><div class="ds-work-heading"><h3>${esc(composerLabel(group.composer))} · ${esc(workLabel(group.work))}</h3><span>${group.records.length}件の譜読み資料</span></div><div class="ds-part-grid">${group.records.map(cardMarkup).join('')}</div></section>`).join('') || '<p class="ds-empty">この条件に合う資料はありません。</p>'}</div>`;
    showBrowser(`${heading}の譜読み`, 'STEP 2', '読みたいパートを選んでください。確認状況と注意点も各資料に表示しています。', html);
    const search = content.querySelector('.ds-search');
    const applyFilter = () => {
      const query = search.value.trim().toLocaleLowerCase();
      let visible = 0;
      content.querySelectorAll('.ds-work-section').forEach((section) => {
        const matchesText = !query || section.textContent.toLocaleLowerCase().includes(query);
        section.hidden = !matchesText;
        if (matchesText) visible++;
      });
      let empty = content.querySelector('.ds-filter-empty');
      if (!visible && !empty) {
        empty = document.createElement('p'); empty.className = 'ds-empty ds-filter-empty'; empty.textContent = '検索に合う資料はありません。';
        content.querySelector('.ds-work-list').append(empty);
      } else if (visible && empty) empty.remove();
    };
    search.addEventListener('input', applyFilter);
    content.querySelector('.ds-search-clear').addEventListener('click', () => { search.value = ''; applyFilter(); search.focus(); });
  }

  selector.querySelectorAll('[data-route]').forEach((button) => button.addEventListener('click', () => renderFacets(button.dataset.route)));
  selector.querySelector('.ds-back').addEventListener('click', () => {
    if (step === 'results') renderFacets(currentRoute);
    else { browser.hidden = true; step = 'home'; selector.querySelector('#selectorTitle').focus?.(); }
  });
  selector.querySelector('.ds-home-button').addEventListener('click', () => { browser.hidden = true; step = 'home'; });
  content.addEventListener('click', (event) => {
    const button = event.target.closest('[data-facet]');
    if (button) renderResults(currentRoute, button.dataset.facet);
  });

  async function loadRecords() {
    try {
      const [readerRes, catalogRes] = await Promise.all([fetch('reader/parts.json'), fetch('catalog.json')]);
      if (!readerRes.ok || !catalogRes.ok) throw new Error('譜読み資料の一覧を読み込めませんでした。');
      const readerData = await readerRes.json();
      const catalogData = await catalogRes.json();
      const readerRecords = readerData.parts.map((part) => ({
        reader: true,
        title: part.title,
        instrument: part.part,
        composer: part.composer,
        composerKey: 'antonin-dvorak',
        work: part.work,
        summary: `${part.subtitle} · ${part.notes}音`,
        reviewStatus: '第三者監査前',
        reviewed: false,
        limitations: [part.status],
        open: `reader/index.html?part=${encodeURIComponent(part.id)}`,
        links: part.pdf ? [{ label: 'PDFを開く', href: publicPath(`public/${part.pdf}`) }] : []
      }));
      const catalogRecords = catalogData.items.map((item) => {
        const pdfs = (item.artifacts || []).filter((artifact) => artifact.kind === 'PDF' && publicPath(artifact.path));
        const otherHtml = (item.artifacts || []).filter((artifact) => artifact.kind === 'HTML' && publicPath(artifact.path));
        const reviewed = item.review_status === 'reviewed';
        const links = [
          ...pdfs.map((artifact) => ({ label: 'PDFを開く', href: publicPath(artifact.path) })),
          ...otherHtml.map((artifact) => ({ label: 'インタラクティブ版', href: publicPath(artifact.path) }))
        ];
        return {
          reader: false,
          title: item.instrument,
          instrument: item.instrument,
          composer: item.composer,
          composerKey: item.composer_key,
          work: item.work,
          summary: item.summary,
          reviewStatus: reviewed ? '目視確認済み · 演奏照合未実施' : '下書き · 要確認',
          reviewed,
          limitations: item.limitations || [],
          open: publicPath(item.html),
          links
        };
      });
      records = [...readerRecords, ...catalogRecords];
      const instrumentCount = new Set(records.map(familyOf)).size;
      counts.innerHTML = `<strong>${records.length}</strong>件の譜読み資料 <span>·</span> <strong>${instrumentCount}</strong>種類の楽器 <span>·</span> PDF・インタラクティブ版を収録`;
    } catch (error) {
      counts.textContent = error.message || '譜読み資料を読み込めませんでした。';
      selector.querySelectorAll('[data-route]').forEach((button) => { button.disabled = true; });
    }
  }

  loadRecords();
})();
