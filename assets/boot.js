// Runs synchronously in <head>, before the first paint.
//
// The page themes itself from prefers-color-scheme; this only reapplies an
// explicit choice the visitor made earlier, and marks the document so the
// stylesheet can show controls that need a script to work.
(() => {
  'use strict';
  const root = document.documentElement;
  root.dataset.js = 'on';
  try {
    const saved = localStorage.getItem('fs.theme');
    if (saved === 'light' || saved === 'dark') root.dataset.theme = saved;
  } catch {
    /* Storage blocked: prefers-color-scheme decides, which is the default anyway. */
  }
})();
