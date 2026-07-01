#!/usr/bin/env node
// Wasilah Quran-60 cloud publisher (runs on GitHub Actions cron, not the Mac).
// At each run: (1) FB catch-up — schedule any FB posts now inside Facebook's ~29-day
// horizon; (2) IG fire — publish any IG reel whose slot time has passed and isn't
// posted yet (self-healing: a missed slot posts on the next run). State in posted.json,
// committed back by the workflow so reruns are idempotent.
const fs = require('fs');
const https = require('https');

const TOKEN = process.env.META_PAGE_TOKEN;
if (!TOKEN) { console.error('Missing META_PAGE_TOKEN env'); process.exit(1); }
const cfg = JSON.parse(fs.readFileSync(__dirname + '/config.json', 'utf8'));
const schedule = JSON.parse(fs.readFileSync(__dirname + '/schedule.json', 'utf8'));
const POSTED_FILE = __dirname + '/posted.json';
const posted = () => { try { return JSON.parse(fs.readFileSync(POSTED_FILE, 'utf8')); } catch { return {}; } };
const save = (p) => fs.writeFileSync(POSTED_FILE, JSON.stringify(p, null, 2));
const GV = cfg.graphVersion || 'v21.0';
const log = (...a) => console.log(...a);

function api(method, endpoint, params) {
  return new Promise((resolve, reject) => {
    const body = new URLSearchParams(params || {}).toString();
    const isGet = method === 'GET';
    const p = `/${GV}/${endpoint}` + (isGet && body ? `?${body}` : '');
    const req = https.request({ hostname: 'graph.facebook.com', path: p, method,
      headers: isGet ? {} : { 'Content-Type': 'application/x-www-form-urlencoded', 'Content-Length': Buffer.byteLength(body) } },
      res => { let d = ''; res.on('data', c => d += c); res.on('end', () => {
        let j; try { j = JSON.parse(d); } catch { return reject(new Error('bad json: ' + d.slice(0, 160))); }
        if (j.error) return reject(new Error(`[${j.error.code}] ${j.error.message}`));
        resolve(j);
      }); });
    req.on('error', reject);
    if (!isGet && body) req.write(body);
    req.end();
  });
}
const sleep = (ms) => new Promise(r => setTimeout(r, ms));

async function fbCatchUp() {
  const state = posted();
  const now = Math.floor(Date.now() / 1000);
  let ok = 0, fail = 0;
  for (const e of schedule) {
    if (state[`fb-${e.nn}`]) continue;
    if (e.epoch < now + 600) continue; // past/too-soon: IG side handles the live window
    try {
      const r = await api('POST', `${cfg.pageId}/videos`, {
        file_url: e.url, description: e.caption, published: 'false',
        scheduled_publish_time: String(e.epoch), access_token: TOKEN,
      });
      state[`fb-${e.nn}`] = { id: r.id, epoch: e.epoch, at: new Date().toISOString() };
      save(state); log(`FB scheduled fb-${e.nn} -> ${e.isoDhaka}`); ok++;
    } catch (err) {
      if (/publish time is invalid/i.test(err.message)) { /* still beyond horizon; try next run */ }
      else { log(`FB fail fb-${e.nn}: ${err.message}`); fail++; }
    }
  }
  log(`FB catch-up: scheduled ${ok}, fail ${fail}`);
}

async function igPublish(e) {
  const create = await api('POST', `${cfg.igUserId}/media`, {
    media_type: 'REELS', video_url: e.url, caption: e.caption, share_to_feed: 'true', access_token: TOKEN,
  });
  const cid = create.id;
  for (let i = 0; i < 30; i++) {
    await sleep(10000);
    const st = await api('GET', `${cid}`, { fields: 'status_code', access_token: TOKEN });
    if (st.status_code === 'FINISHED') break;
    if (st.status_code === 'ERROR') throw new Error('container ERROR');
    if (i === 29) throw new Error('not FINISHED after 5min');
  }
  const pub = await api('POST', `${cfg.igUserId}/media_publish`, { creation_id: cid, access_token: TOKEN });
  return pub.id;
}

async function igFireDue() {
  const state = posted();
  const now = Math.floor(Date.now() / 1000);
  const due = schedule.filter(e => e.epoch <= now && !state[`ig-${e.nn}`]);
  if (!due.length) { log('IG: nothing due.'); return; }
  log(`IG: ${due.length} due.`);
  for (const e of due) {
    try {
      const id = await igPublish(e);
      state[`ig-${e.nn}`] = { id, epoch: e.epoch, at: new Date().toISOString() };
      save(state); log(`IG published ig-${e.nn} -> ${id}`);
    } catch (err) { log(`IG fail ig-${e.nn}: ${err.message}`); }
  }
}

(async () => {
  log('run at', new Date().toISOString());
  await fbCatchUp();
  await igFireDue();
  const s = posted();
  const fb = schedule.filter(e => s[`fb-${e.nn}`]).length;
  const ig = schedule.filter(e => s[`ig-${e.nn}`]).length;
  log(`status: FB ${fb}/${schedule.length}, IG ${ig}/${schedule.length}`);
})();
