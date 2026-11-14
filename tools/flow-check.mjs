#!/usr/bin/env node
// Drives a real browser over the one thing CSS cannot prove on its own: the
// whole card is a link to the project, every empty pixel of it included, the
// Source link below it still goes to GitHub, and the install command is not
// swallowed by the overlay.
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

async function open({ plantCss, ...options } = {}) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, ...options });
  const page = await context.newPage();
  // The self-checks below plant a known bug in the real stylesheet. Served
  // from the file, it goes through the page's own CSP like the original.
  if (plantCss) {
    await page.route(`${base}/assets/home.css`, async (route) => {
      const css = await readFile(join(ROOT, 'assets/home.css'), 'utf8');
      await route.fulfill({ status: 200, contentType: 'text/css; charset=utf-8', body: `${css}\n${plantCss}\n` });
    });
  }
  // Everything off the local server is answered here: clicks are measured by
  // the URL the browser asked for, and no request reaches the internet.
  await page.route('**/*', (route) => {
    if (route.request().url().startsWith(base)) return route.fallback();
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

// ------------------------------------------------------------ hit-test
// "Click anywhere on the card" is checked pixel by pixel, not at a couple of
// chosen points: every ~6px across each card, whatever the browser puts on
// top has to be the card's own link (its stretched ::after) or one of the
// three controls deliberately lifted above it. A lifted row — .links or
// .install with a z-index — shows up here as a dead strip, and a hover
// effect that moves the card shows up in the hovered pass.
const STEP = 6;
const LIFTED = '.src, .install code, .copy';

/** The sample grid of a card in viewport coordinates: every STEP px, plus
 *  the last row and column, two pixels in from the edge (the 1px border is
 *  the card's, not the link's), so the edges themselves are always tested. */
function grid(box) {
  const axis = (from, to) => {
    const points = [];
    for (let at = from + 2; at <= to - 2; at += STEP) points.push(at);
    if (to - 2 - points[points.length - 1] > 0.5) points.push(to - 2);
    return points;
  };
  const xs = axis(box.left, box.right);
  return axis(box.top, box.bottom).flatMap((y) => xs.map((x) => ({ x, y })));
}

/** What is on top at (x, y), and whether it reaches the card's link. */
function probe(element, [points, lifted, left, top]) {
  const go = element.querySelector('.name .go');
  const misses = [];
  for (const { x, y } of points) {
    const hit = document.elementFromPoint(x, y);
    if (hit && go.contains(hit)) continue;
    const control = hit?.closest(lifted);
    if (control && element.contains(control)) continue;
    const what = !hit ? 'nothing'
      : hit.tagName.toLowerCase() + (hit.className ? '.' + String(hit.className).split(' ')[0] : '');
    misses.push({ x: Math.round(x - left), y: Math.round(y - top), what });
  }
  return misses;
}

const settle = (page) => page.evaluate(() =>
  Promise.all(document.getAnimations().map((animation) => animation.finished)));

/**
 * Every sample point in every card that does not reach the card's link.
 *
 * hover: false reads the page at rest, all points of a card in one go.
 *
 * hover: true reads it the way a mouse sees it, because :hover can move the
 * card out from under the pointer (a translateY lift leaves the bottom edge
 * behind). A pointer on any point of the card's resting box hovers the card,
 * so the card is put in :hover through DevTools (CSS.forcePseudoState), its
 * transitions are let finish, and every grid point is probed in that state.
 * On top of that the real mouse is moved onto each point of the card's last
 * row and last column, the edges a lift or a shift uncovers, and each is
 * probed where it lands. A real move costs a frame (~16 ms), which is why it
 * is not spent on all ~50 000 points at 1280 px. The grid is always the
 * card's resting box, which is where a visitor aims.
 */
async function deadPoints(page, { hover = false } = {}) {
  const dead = [];
  const count = await page.locator('.card').count();
  let cdp = null;
  let cardNodes = [];
  if (hover) {
    cdp = await page.context().newCDPSession(page);
    await cdp.send('DOM.enable');
    await cdp.send('CSS.enable');
    const { root } = await cdp.send('DOM.getDocument', { depth: -1 });
    ({ nodeIds: cardNodes } = await cdp.send('DOM.querySelectorAll', { nodeId: root.nodeId, selector: '.card' }));
  }
  for (let index = 0; index < count; index += 1) {
    const card = page.locator('.card').nth(index);
    await card.scrollIntoViewIfNeeded();
    await page.mouse.move(0, 0);
    await settle(page);
    const box = await card.evaluate((element) => {
      const { left, top, right, bottom } = element.getBoundingClientRect();
      return { left, top, right, bottom };
    });
    const points = grid(box);
    const misses = [];
    if (!hover) {
      misses.push(...await card.evaluate(probe, [points, LIFTED, box.left, box.top]));
    } else {
      const nodeId = cardNodes[index];
      await cdp.send('CSS.forcePseudoState', { nodeId, forcedPseudoClasses: ['hover'] });
      await settle(page);
      misses.push(...(await card.evaluate(probe, [points, LIFTED, box.left, box.top]))
        .map((miss) => ({ ...miss, what: `${miss.what}, card hovered` })));
      await cdp.send('CSS.forcePseudoState', { nodeId, forcedPseudoClasses: [] });
      await page.mouse.move(0, 0);
      await settle(page);

      const lastY = Math.max(...points.map((point) => point.y));
      const lastX = Math.max(...points.map((point) => point.x));
      const edges = points.filter((point) => point.y === lastY || point.x === lastX);
      for (const point of edges) {
        await page.mouse.move(point.x, point.y);
        await settle(page);
        misses.push(...(await card.evaluate(probe, [[point], LIFTED, box.left, box.top]))
          .map((miss) => ({ ...miss, what: `${miss.what}, mouse on it` })));
      }
    }
    // A point both passes probe counts once.
    const unique = [...new Map(misses.map((miss) => [`${miss.x},${miss.y}`, miss])).values()];
    if (unique.length) dead.push({ name: items[index]?.name ?? `card ${index + 1}`, total: points.length, misses: unique });
  }
  if (cdp) await cdp.detach();
  return dead;
}

/** One fail line per card, with the first dead point as the example. */
function report(dead, label) {
  if (!dead.length) pass(`${label}: no dead point in any card`);
  for (const card of dead) {
    const first = card.misses[0];
    fail(`${label}: ${card.name} has ${card.misses.length}/${card.total} dead points, e.g. (${first.x}, ${first.y}) hits <${first.what}>`);
  }
  return dead.reduce((sum, card) => sum + card.misses.length, 0);
}

// Phones, the two-column tablet range, and desktop.
const VIEWPORTS = [320, 390, 768, 900, 1280];
const SCHEMES = ['light', 'dark'];
// Where a mouse is likely, so where :hover is: the hovered pass runs here.
const HOVER_VIEWPORTS = [768, 1024, 1280];

console.log(`hit-test — every ${STEP}px of every card opens it, at ${VIEWPORTS.join(', ')} px, light and dark`);
for (const width of VIEWPORTS) {
  for (const colorScheme of SCHEMES) {
    const { context, page } = await open({ viewport: { width, height: 900 }, colorScheme });
    report(await deadPoints(page), `${width}px ${colorScheme}`);
    // Same pass, same widths: a group whose cards do not fill their last row
    // leaves an empty track that reads as a missing project.
    const rows = await page.locator('.cards').evaluateAll((lists) => lists.map((list) => ({
      group: list.closest('.group')?.querySelector('h2')?.textContent ?? '?',
      cards: list.children.length,
      columns: getComputedStyle(list).gridTemplateColumns.split(' ').length,
    })));
    const ragged = rows.filter((row) => row.cards % row.columns !== 0);
    if (!ragged.length) pass(`${width}px ${colorScheme}: every group fills its last row`);
    for (const row of ragged) fail(`${width}px ${colorScheme}: ${row.group} puts ${row.cards} cards in ${row.columns} columns and leaves a gap`);
    await context.close();
  }
}

// Theme does not move anything, so one scheme is enough for the hovered pass.
console.log(`hit-test, hovered — each card in :hover, the real mouse on its edges, at ${HOVER_VIEWPORTS.join(', ')} px`);
for (const width of HOVER_VIEWPORTS) {
  const { context, page } = await open({ viewport: { width, height: 900 } });
  report(await deadPoints(page, { hover: true }), `${width}px hovered`);
  await context.close();
}

// The hit-test has to bite. Put back each bug it was written for and it must
// report the cards that bug breaks. If it stays quiet, the test is broken,
// not the page.
console.log('hit-test self-check — a lifted .links / .install row must be caught');
{
  const { context, page } = await open({
    viewport: { width: 390, height: 900 },
    plantCss: '.links, .install { position: relative; z-index: 2; }',
  });
  const dead = await deadPoints(page);
  const expected = await page.locator('.card').filter({ has: page.locator('.links, .install') }).count();
  if (expected > 0 && dead.length === expected) {
    pass(`with the rows lifted, the hit-test flags all ${expected} cards that have one`);
  } else {
    fail(`with the rows lifted, the hit-test flagged ${dead.length} cards, expected ${expected}: it would not catch the regression`);
  }
  await context.close();
}

console.log('hit-test self-check — a translateY hover lift must be caught by the hovered pass');
{
  const { context, page } = await open({
    viewport: { width: 1280, height: 900 },
    plantCss: '@media (min-width: 680px) { .card { transition: transform 0.15s ease; } .card:hover { transform: translateY(-2px); } }',
  });
  const dead = await deadPoints(page, { hover: true });
  const expected = await page.locator('.card').count();
  if (dead.length === expected) {
    const points = dead.reduce((sum, card) => sum + card.misses.length, 0);
    pass(`with the hover lift back, the hovered pass flags all ${expected} cards (${points} dead points)`);
  } else {
    fail(`with the hover lift back, the hovered pass flagged ${dead.length} of ${expected} cards: it would not catch the regression`);
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
