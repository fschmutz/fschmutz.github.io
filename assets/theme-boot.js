// Loaded synchronously in <head> so the first paint already uses the right theme.
// The markup ships with class="dark": dark is the default, light is opt-in.
(() => {
  'use strict';
  try {
    if (localStorage.getItem('fs.theme') === 'light') {
      document.documentElement.classList.remove('dark');
    }
  } catch {
    /* Private mode or blocked storage: keep the dark default. */
  }
})();
