// Two optional enhancements: the theme toggle and the copy buttons. Both are
// hidden until this file runs, so nothing on the page is inert without it.
(() => {
  'use strict';

  const root = document.documentElement;
  const live = document.getElementById('live');

  const announce = (message) => {
    if (!live) return;
    live.textContent = '';
    // Re-setting the same text would not be announced again.
    requestAnimationFrame(() => { live.textContent = message; });
  };

  /* ------------------------------------------------------------- theme */

  const button = document.getElementById('theme');
  if (button) {
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)');
    const sun = button.querySelector('.i-sun');
    const moon = button.querySelector('.i-moon');
    const label = document.getElementById('theme-label');

    const effective = () => root.dataset.theme || (prefersDark.matches ? 'dark' : 'light');

    const paint = () => {
      const dark = effective() === 'dark';
      // The icon shows where the next click goes, not where you are.
      sun.toggleAttribute('hidden', !dark);
      moon.toggleAttribute('hidden', dark);
      const text = dark ? 'Switch to the light theme' : 'Switch to the dark theme';
      label.textContent = text;
      button.title = text;
    };

    button.addEventListener('click', () => {
      const next = effective() === 'dark' ? 'light' : 'dark';
      root.dataset.theme = next;
      try {
        localStorage.setItem('fs.theme', next);
      } catch {
        /* Nothing to remember it with; the choice still holds for this page view. */
      }
      paint();
      announce(next === 'dark' ? 'Dark theme.' : 'Light theme.');
    });

    // Follow the system while the visitor has not overridden it.
    prefersDark.addEventListener('change', () => { if (!root.dataset.theme) paint(); });

    button.hidden = false;
    paint();
  }

  /* -------------------------------------------------------------- copy */

  for (const copy of document.querySelectorAll('.copy')) {
    const source = document.getElementById(copy.dataset.copy);
    if (!source || !navigator.clipboard) continue;

    copy.hidden = false;
    copy.addEventListener('click', async () => {
      try {
        await navigator.clipboard.writeText(source.textContent.trim());
      } catch {
        announce('Could not copy. Select the command and copy it yourself.');
        return;
      }
      copy.firstChild.nodeValue = 'Copied';
      announce('Install command copied.');
      setTimeout(() => { copy.firstChild.nodeValue = 'Copy'; }, 1800);
    });
  }
})();
