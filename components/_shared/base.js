// Shared base stylesheet for ui-* components. Not a component.
//
// Defines private variables (--_bg, --_text, ...) on :host. Each reads the public
// token (--ui-color-*, see tokens.css) and falls back to a built-in light/dark value,
// so components theme without edits and still render with no tokens.css loaded.
//
// Exports:
//   baseCss        string of CSS to put first in a component's styles
//   sheet(...css)  build a constructable stylesheet from baseCss + component CSS

export const baseCss = `
:host {
  --_bg: var(--ui-color-bg, light-dark(#ffffff, #0f1117));
  --_surface: var(--ui-color-surface, light-dark(#ffffff, #161b22));
  --_surface-2: var(--ui-color-surface-2, light-dark(#f4f5f7, #1c2128));
  --_text: var(--ui-color-text, light-dark(#1b1f24, #e1e4e8));
  --_muted: var(--ui-color-muted, light-dark(#5f6b7a, #8b949e));
  --_border: var(--ui-color-border, light-dark(#d0d7de, #30363d));
  --_accent: var(--ui-color-accent, light-dark(#1f6feb, #388bfd));
  --_on-accent: var(--ui-color-on-accent, light-dark(#ffffff, #0f1117));
  --_danger: var(--ui-color-danger, light-dark(#cf222e, #f85149));
  --_success: var(--ui-color-success, light-dark(#1a7f37, #3fb950));
  --_space: var(--ui-space, 12px);
  --_radius: var(--ui-radius, 8px);
  --_font: var(--ui-font, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif);
  --_font-size: var(--ui-font-size, 0.95rem);
  font-family: var(--_font);
  font-size: var(--_font-size);
  color: var(--_text);
}
*, *::before, *::after { box-sizing: border-box; }
[hidden] { display: none !important; }
button { font: inherit; color: inherit; cursor: pointer; touch-action: manipulation; }
button:focus-visible, input:focus-visible, textarea:focus-visible, .focusable:focus-visible {
  outline: 2px solid var(--_accent);
  outline-offset: 2px;
}
.icon-btn {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 2rem; min-height: 2rem; padding: 0;
  background: none; border: 1px solid transparent; border-radius: calc(var(--_radius) - 2px);
  color: var(--_muted);
}
.icon-btn:hover { color: var(--_text); border-color: var(--_border); }
.icon-btn svg { width: 1.1rem; height: 1.1rem; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation-duration: 0.01ms !important; transition-duration: 0.01ms !important; transition-delay: 0s !important; }
}
`;

export const sheet = (...css) => {
  const s = new CSSStyleSheet();
  s.replaceSync([baseCss, ...css].join('\n'));
  return s;
};
