// Web Speech API wrapper (speech-to-text). Not a component.
//
// No backend and no API key: it uses the browser's built-in SpeechRecognition
// (webkitSpeechRecognition in Chrome/Safari). Feature-detect before showing UI.
//
// Exports:
//   speechSupported()             boolean
//   createDictation(options)      -> { start(), stop(), toggle(), listening }
//     options.lang                BCP-47 tag, default: document language or the browser's
//     options.onResult(text, isFinal)   interim and final transcript chunks
//     options.onState(listening)        fired when listening starts/stops
//     options.onError(code)             SpeechRecognition error code, e.g. "not-allowed"

const Ctor = () => window.SpeechRecognition || window.webkitSpeechRecognition;

export const speechSupported = () => !!Ctor();

export function createDictation({ lang, onResult, onState, onError } = {}) {
  let rec = null;
  let listening = false;

  const setListening = (v) => {
    if (listening === v) return;
    listening = v;
    onState?.(v);
  };

  const start = () => {
    const SR = Ctor();
    if (!SR || listening) return;
    rec = new SR();
    rec.lang = (typeof lang === 'function' ? lang() : lang) || document.documentElement.lang || navigator.language || 'en-US';
    rec.interimResults = true;
    rec.continuous = false;
    rec.onstart = () => setListening(true);
    rec.onend = () => { setListening(false); rec = null; };
    rec.onerror = (e) => onError?.(e.error);
    rec.onresult = (e) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        onResult?.(r[0].transcript.trim(), r.isFinal);
      }
    };
    try { rec.start(); } catch (err) { onError?.(String(err)); }
  };

  const stop = () => { try { rec?.stop(); } catch { /* already stopped */ } };

  return {
    start,
    stop,
    toggle: () => (listening ? stop() : start()),
    get listening() { return listening; },
  };
}
