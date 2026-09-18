const { chromium } = require('playwright');
const fs = require('fs');
const http = require('http');
const path = require('path');

// 網頁版端對端測試：node test_web.js（需先 npm i playwright 並安裝 chromium）
// 可用環境變數 PW_CHROMIUM 指定 Chromium 執行檔路徑。
const WEB = path.resolve(__dirname, '..');
const REPO = path.resolve(__dirname, '..', '..');
const OUT = path.resolve(__dirname, 'out');
fs.mkdirSync(OUT, { recursive: true });

function serve() {
  return new Promise(res => {
    const srv = http.createServer((req, r) => {
      const p = path.join(WEB, req.url === '/' ? 'index.html' : req.url);
      fs.readFile(p, (e, d) => { if (e) { r.writeHead(404); r.end(); } else { r.writeHead(200, { 'content-type': 'text/html; charset=utf-8' }); r.end(d); } });
    }).listen(0, () => res(srv));
  });
}
let fails = 0;
const check = (cond, msg) => { console.log((cond ? 'PASS ' : 'FAIL ') + msg); if (!cond) fails++; };

(async () => {
  const srv = await serve(); const url = `http://127.0.0.1:${srv.address().port}/`;
  const browser = await chromium.launch(process.env.PW_CHROMIUM ? { executablePath: process.env.PW_CHROMIUM } : {});
  const ctx = await browser.newContext({ viewport: { width: 1100, height: 800 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', e => errors.push('pageerror: ' + e.message));
  page.on('console', m => { if (m.type() === 'error') errors.push('console: ' + m.text()); });
  await page.goto(url); await page.waitForFunction(() => window.__sb && window.__sb.app.db.db);

  const docx = fs.readFileSync(path.join(REPO, 'booklet/永續企業治理小冊子_A5.docx'));
  const png = fs.readFileSync(path.join(REPO, 'booklet/img/cover.png'));
  const big5 = Buffer.from('\xB3o\xACO Big5 \xC2\xC2\xC0\xC9\xA1A\xB8\xB3\xA8\xC6\xB7|\xA8M\xC4\xB3', 'latin1'); // 這是 Big5 舊檔，董事會決議
  const entries = [
    { path: 'D/文件/2024/永續治理筆記.txt', name: '永續治理筆記.txt', size: 0, mtime: Date.now() - 864e5, data: Buffer.from('永續企業治理的三個線索：金剛組、柯達與富士、屏東基督教醫院。') },
    { path: 'D/文件/report_q3.md', name: 'report_q3.md', size: 0, mtime: Date.now() - 3 * 864e5, data: Buffer.from('quarterly report\nrevenue grew 12%\n') },
    { path: 'D/文件/舊檔.txt', name: '舊檔.txt', size: 0, mtime: Date.now() - 400 * 864e5, data: big5 },
    { path: 'D/文件/2024/永續企業治理小冊子_A5.docx', name: '永續企業治理小冊子_A5.docx', size: 0, mtime: Date.now(), data: docx },
    { path: 'D/照片/封面.png', name: '封面.png', size: 0, mtime: Date.now(), data: png },
    { path: 'D/照片/封面 (複本).png', name: '封面 (複本).png', size: 0, mtime: Date.now(), data: png },
    { path: 'D/node_modules/x/a.js', name: 'a.js', size: 0, mtime: Date.now(), data: Buffer.from('ignored') },
    { path: 'D/文件/x.tmp', name: 'x.tmp', size: 0, mtime: Date.now(), data: Buffer.from('tmp') },
  ].map(e => ({ ...e, size: e.data.length, data: Array.from(e.data) }));

  const scanMs = await page.evaluate(async entries => {
    const t0 = performance.now();
    await window.__sb.scanMemory('D', entries.map(e => ({ ...e, data: new Uint8Array(e.data) })));
    return Math.round(performance.now() - t0);
  }, entries);
  console.log('scan ms (in page)', scanMs);
  const count = await page.evaluate(() => window.__sb.app.meta.size);
  check(count === 6, `indexed 6 files (got ${count}; node_modules and .tmp skipped)`);

  const s = async (q, f) => page.evaluate(([q, f]) => window.__sb.search(q, f).then(r => r.results.map(x => x.m.name)), [q, f || {}]);
  let r = await s('永續 治理'); check(r.includes('永續治理筆記.txt') && r.includes('永續企業治理小冊子_A5.docx') && !r.includes('report_q3.md'), `中文搜尋 永續 治理 → ${r}`);
  r = await s('董事會'); check(r.includes('舊檔.txt') && r.includes('永續企業治理小冊子_A5.docx'), `Big5 + docx 內文 董事會 → ${r}`);
  r = await s('金剛組'); check(r.includes('永續企業治理小冊子_A5.docx') && r.includes('永續治理筆記.txt'), `docx 內文 金剛組 → ${r}`);
  r = await s('reven'); check(r.length === 1 && r[0] === 'report_q3.md', `英文前綴 reven → ${r}`);
  r = await s('封面', { kind: '圖片' }); check(r.length === 2, `檔名 + 類型過濾 → ${r}`);
  r = await s('不存在的詞彙'); check(r.length === 0, '無結果');
  r = await s(''); check(r.length === 6, `空查詢列出全部 (${r.length})`);

  // UI: 搜尋列
  await page.click('button[data-tab="search"]');
  await page.fill('#q', '董事會'); await page.waitForTimeout(400);
  const html = await page.innerHTML('#searchResults');
  check(html.includes('<mark>董事會</mark>'), 'UI 結果含 highlight');
  await page.screenshot({ path: OUT + '/shot_search.png' });

  // 詳情：標籤 + 筆記
  await page.click('.result[data-id]'); await page.waitForSelector('#dlg[open]');
  await page.fill('#dTagInput', '工作 季報'); await page.press('#dTagInput', 'Enter'); await page.waitForTimeout(200);
  await page.fill('#dNoteInput', '這是給董事會看的版本，很重要'); await page.click('#dNoteForm button'); await page.waitForTimeout(200);
  const dlgText = await page.textContent('#dlg');
  check(dlgText.includes('#工作') && dlgText.includes('#季報') && dlgText.includes('很重要'), '標籤與筆記顯示');
  await page.screenshot({ path: OUT + '/shot_detail.png' });
  await page.click('#dClose');
  r = await s('季報'); check(r.length === 1, `標籤可搜尋 → ${r}`);
  r = await s('很重要'); check(r.length === 1, `筆記可搜尋 → ${r}`);
  r = await s('董事會', { tag: '工作' }); check(r.length === 1, `標籤過濾 → ${r}`);

  // 增量：改一個檔、刪一個檔
  const entries2 = entries.filter(e => e.name !== '舊檔.txt').map(e => e.name === 'report_q3.md' ? { ...e, data: Array.from(Buffer.from('now about 第二大腦\n')), size: 20, mtime: Date.now() } : e);
  await page.evaluate(async entries => { const root = window.__sb.app.roots[0]; root.entries = entries.map(e => ({ ...e, data: new Uint8Array(e.data) })); await window.__sb.app.scan(root); }, entries2);
  r = await s('第二大腦'); check(r.length === 1 && r[0] === 'report_q3.md', `增量更新內文 → ${r}`);
  r = await s('revenue'); check(r.length === 0, '舊內文已移出索引');
  r = await s('董事會'); check(!r.includes('舊檔.txt'), `消失的檔案預設不顯示 → ${r}`);
  r = await s('董事會', { missing: true }); check(r.includes('舊檔.txt'), `--含已消失 → ${r}`);
  r = await s('季報'); check(r.length === 1, '標籤在重掃後保留');
  await page.click('button[data-tab="search"]');

  // 重新載入：索引與資料持久化
  await page.reload(); await page.waitForFunction(() => window.__sb && window.__sb.app.meta.size > 0);
  await page.evaluate(entries => { window.__sb.app.roots[0].entries = entries.map(e => ({ ...e, data: new Uint8Array(e.data) })); }, entries2);
  r = await s('金剛組'); check(r.length === 2, `重載後仍可搜尋 → ${r}`);
  const idx = await page.evaluate(() => window.__sb.app.index.map.size); check(idx > 100, `索引詞數 ${idx}`);

  // 統計 / 重複檔 / 標籤頁
  await page.click('button[data-tab="stats"]'); await page.waitForTimeout(200);
  const tiles = await page.textContent('#tiles'); check(tiles.includes('檔案') && tiles.includes('總大小'), '統計面板');
  await page.screenshot({ path: OUT + '/shot_stats.png', fullPage: true });
  await page.click('button[data-tab="dupes"]'); await page.selectOption('#dupMin', '0'); await page.click('#btnDupes');
  await page.waitForFunction(() => document.querySelector('#dupStatus').textContent.startsWith('共'));
  console.log('  dupStatus:', await page.textContent('#dupStatus'));
  const dup = await page.textContent('#dupResults'); check(dup.includes('封面.png') && dup.includes('封面 (複本).png') && !dup.includes('report'), '重複檔偵測（SHA-256）');
  await page.click('button[data-tab="tags"]'); await page.waitForTimeout(200);
  const tg = await page.textContent('#tagCloud'); check(tg.includes('#工作'), '標籤頁');

  // 匯出 Markdown / 備份
  await page.click('button[data-tab="export"]');
  const [dl] = await Promise.all([page.waitForEvent('download'), page.click('#btnExportMd')]);
  const md = fs.readFileSync(await dl.path(), 'utf8'); check(md.includes('# 我的第二大腦') && md.includes('## 標籤') && md.includes('永續治理筆記.txt'), 'Markdown 匯出');
  const [dl2] = await Promise.all([page.waitForEvent('download'), page.click('#btnBackup')]);
  const bk = JSON.parse(fs.readFileSync(await dl2.path(), 'utf8')); check(bk.files.length === 6 && bk.files.some(f => f.notes && f.notes.length), 'JSON 備份');

  // 手機寬度版面
  const mob = await ctx.newPage(); await mob.setViewportSize({ width: 390, height: 800 }); await mob.goto(url); await mob.waitForFunction(() => window.__sb && window.__sb.app.meta.size > 0);
  await mob.fill('#q', '永續'); await mob.waitForTimeout(400); await mob.screenshot({ path: OUT + '/shot_mobile.png' });
  const overflow = await mob.evaluate(() => document.documentElement.scrollWidth > window.innerWidth + 1); check(!overflow, '手機寬度無水平捲動');
  // 深色模式
  await mob.emulateMedia({ colorScheme: 'dark' }); await mob.screenshot({ path: OUT + '/shot_mobile_dark.png' });

  console.log('errors:', errors.length ? errors : 'none'); if (errors.length) fails++;
  await browser.close(); srv.close();
  console.log(fails ? `\n${fails} FAILED` : '\nALL PASSED'); process.exit(fails ? 1 : 0);
})().catch(e => { console.error(e); process.exit(2); });
