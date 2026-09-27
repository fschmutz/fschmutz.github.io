// Light/dark toggle. The choice is remembered per browser; dark stays the default.
(() => {
  'use strict';
  const root = document.documentElement;
  const button = document.getElementById('theme');
  if (!button) return;

  const sun = document.getElementById('icon-sun');
  const moon = document.getElementById('icon-moon');

  const paint = () => {
    const dark = root.classList.contains('dark');
    button.setAttribute('aria-pressed', String(dark));
    button.setAttribute('aria-label', dark ? 'Switch to the light theme' : 'Switch to the dark theme');
    // SVG elements have no `hidden` IDL property, so drive the attribute directly.
    if (sun) sun.toggleAttribute('hidden', !dark);
    if (moon) moon.toggleAttribute('hidden', dark);
  };

  button.addEventListener('click', () => {
    const dark = root.classList.toggle('dark');
    try {
      localStorage.setItem('fs.theme', dark ? 'dark' : 'light');
    } catch {
      /* Nothing to remember it with: the toggle still works for this page view. */
    }
    paint();
  });

  paint();
})();
