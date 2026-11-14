#!/usr/bin/env node
// Drives a real browser over the one thing CSS cannot prove on its own: the
// whole card is a link to the project, the Source link below it still goes to
// GitHub, and the install command is not swallowed by the overlay.
//
//     npm ci && npx playwright install chromium && node tools/flow-check.mjs
//
// Nothing leaves the machine. A static server runs out of the repository root
// and every request that is not to it is answered with a stub, so a click on
// an external link is observed by where the browser tried to go.

import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { dirname, join, normalize, resolve } from 'node:path';
import { chromium } from 'playwright';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.xml': 'application/xml; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
};

const failures = [];
const pass = (message) => console.log(`  ok    ${message}`);
const fail = (message) => { failures.push(message); console.log(`  FAIL  ${message}`); };

async function serve() {
  const server = createServer(async (request, response) => {
    const path = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
    const file = join(ROOT, normalize(path === '/' ? '/index.html' : path));
    if (!file.startsWith(ROOT)) { response.writeHead(403).end(); return; }
    try {
      const body = await readFile(file);
      const extension = file.slice(file.lastIndexOf('.'));
      response.writeHead(200, { 'content-type': TYPES[extension] ?? 'application/octet-stream' });
      response.end(body);
    } catch {
      response.writeHead(404, { 'content-type': 'text/html' }).end('not found');
    }
  });
  await new Promise((done) => server.listen(0, '127.0.0.1', done));
  return { server, base: `http://127.0.0.1:${server.address().port}` };
}

const projects = JSON.parse(await readFile(join(ROOT, 'projects.json'), 'utf8'));
const items = projects.groups.flatMap((group) => group.items);
const { server, base } = await serve();
const browser = await chromium.launch();

async function open(options = {}) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, ...options });
  const page = await context.newPage();
  // Everything off the local server is answered here: clicks are measured by
  // the URL the browser asked for, and no request reaches the internet.
  await page.route('**/*', (route) => {
    if (route.request().url().startsWith(base)) return route.continue();
    return route.fulfill({ status: 200, contentType: 'text/html', body: '<!doctype html><title>stub</title>' });
  });
  await page.goto(base + '/', { waitUntil: 'networkidle' });
  return { context, page };
}

async function navigatesTo(page, expected, act) {
  let arrived = false;
  try {
    await Promise.all([page.waitForURL(expected, { timeout: 5000 }), act()]);
    arrived = true;
  } catch {
    arrived = false;
  }
  // Back to a known state: history after a stubbed navigation is not worth trusting.
  await page.goto(base + '/', { waitUntil: 'networkidle' });
  return arrived;
}

/** Click a point, not an element: the overlay is meant to be in the way. */
const clickAt = (page, x, y) => () => page.mouse.click(x, y);

console.log(`cards — ${items.length} projects, served from ${base}`);
{
  const { context, page } = await open();
  const count = await page.locator('.card').count();
  if (count !== items.length) fail(`the page has ${count} cards, projects.json has ${items.length}`);

  for (const [index, item] of items.entries()) {
    const card = page.locator('.card').nth(index);
    // Mouse coordinates are viewport coordinates, so the card has to be in it.
    await card.scrollIntoViewIfNeeded();
    const box = await card.boundingBox();

    // An empty corner of the card, clear of the heading, the summary and
    // every control: the stretched ::after is the only thing under it.
    const corner = { x: box.x + box.width - 9, y: box.y + 7 };
    const under = await page.evaluate(
      ([x, y]) => {
        const element = document.elementFromPoint(x, y);
        const link = element?.closest('a');
        return { tag: element?.tagName.toLowerCase(), href: link?.getAttribute('href') ?? null };
      },
      [corner.x, corner.y],
    );
    if (under.href === item.url) pass(`${item.name}: the card's empty corner belongs to ${item.url}`);
    else fail(`${item.name}: the corner hit <${under.tag}> for ${under.href}, expected ${item.url}`);

    if (await navigatesTo(page, item.url, clickAt(page, corner.x, corner.y))) {
      pass(`${item.name}: clicking the corner opened ${item.url}`);
    } else {
      fail(`${item.name}: clicking the corner did not open ${item.url}`);
    }

    // And the middle of the thumbnail, which is the obvious place to aim.
    await page.locator('.card').nth(index).scrollIntoViewIfNeeded();
    const thumb = await page.locator('.card').nth(index).locator('.thumb').boundingBox();
    const middle = { x: thumb.x + thumb.width / 2, y: thumb.y + thumb.height / 2 };
    if (await navigatesTo(page, item.url, clickAt(page, middle.x, middle.y))) {
      pass(`${item.name}: clicking the thumbnail opened ${item.url}`);
    } else {
      fail(`${item.name}: clicking the thumbnail did not open ${item.url}`);
    }

    const source = page.locator('.card').nth(index).locator('.src');
    if (item.source === item.url) {
      if (await source.count()) fail(`${item.name}: Source repeats the card's own link and should be dropped`);
      else pass(`${item.name}: no Source link, because it would repeat the card link`);
      continue;
    }
    if (await navigatesTo(page, item.source, () => source.click())) {
      pass(`${item.name}: Source opened ${item.source}`);
    } else {
      fail(`${item.name}: Source did not open ${item.source}`);
    }
  }
  await context.close();
}

console.log('install row — stays above the overlay');
{
  const { context, page } = await open({ permissions: ['clipboard-read', 'clipboard-write'] });
  const code = page.locator('.install code').first();
  const card = page.locator('.card').filter({ has: page.locator('.install') }).first();
  const expected = await card.locator('.name .go').getAttribute('href');

  await code.click();
  await page.waitForTimeout(400);
  if (page.url().startsWith(base)) pass('clicking the install command does not follow the card link');
  else fail(`clicking the install command navigated to ${page.url()} instead of staying put (card link is ${expected})`);

  const copy = card.locator('.copy');
  await copy.click();
  await page.waitForTimeout(400);
  const copied = await page.evaluate(() => navigator.clipboard.readText());
  const wanted = (await code.textContent()).trim();
  if (!page.url().startsWith(base)) fail(`the Copy button navigated to ${page.url()}`);
  else if (copied === wanted) pass(`Copy put ${JSON.stringify(wanted)} on the clipboard and stayed on the page`);
  else fail(`Copy wrote ${JSON.stringify(copied)}, expected ${JSON.stringify(wanted)}`);
  await context.close();
}

console.log('keyboard — card link, then its Source link');
{
  const { context, page } = await open();
  for (const index of [0, 1, items.length - 1]) {
    const card = page.locator('.card').nth(index);
    await card.locator('.name .go').focus();
    const first = await page.evaluate(() => document.activeElement.getAttribute('href'));
    await page.keyboard.press('Tab');
    const second = await page.evaluate(() => ({
      href: document.activeElement.getAttribute('href'),
      klass: document.activeElement.className,
    }));
    const item = items[index];
    if (first !== item.url) {
      fail(`card ${index + 1}: focusing the heading link reached ${first}, expected ${item.url}`);
    } else if (second.klass.includes('src') && second.href === item.source) {
      pass(`card ${index + 1}: Tab goes ${item.url} → Source (${item.source})`);
    } else {
      fail(`card ${index + 1}: after the card link Tab reached ${second.href}, expected Source ${item.source}`);
    }
  }
  await context.close();
}

await browser.close();
server.close();

console.log();
if (failures.length) {
  console.log(`${failures.length} failure(s):`);
  for (const failure of failures) console.log(`  - ${failure}`);
  process.exit(1);
}
console.log('all card flows behave');
