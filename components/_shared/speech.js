// Speech-to-text wrapper. Not a component.
//
// Two paths, same callbacks:
//   native   the browser's SpeechRecognition (webkitSpeechRecognition in Chrome/Safari). No backend, no key.
//   backend  MediaRecorder + a host-supplied transcriber. Used when SpeechRecognition is missing
//            (e.g. Firefox) or when forced with speech="backend". No interim results.
//
// Components never pick a URL or make network calls: the host registers one function with
// setTranscriber() and owns all fetch/auth/URL logic. Feature-detect before showing UI.
//
// Exports:
//   setTranscriber(fn|null)       global backend; fn = async (blob, {mime, lang}) => text
//                                 (the backend must accept both audio/webm;codecs=opus (Chrome)
//                                 and audio/mp4 (iPad Safari))
//   getTranscriber()              the registered function or null
//   speechSource(mode, transcriber)  "native" | "backend" | null: what would run.
//                                 mode "auto" (default): native if available, else backend if a
//                                 transcriber is set; "native": native only; "backend": backend only
//   speechSupported(mode, transcriber)  boolean, speechSource(...) !== null
//   createDictation(options)      -> { start(), stop(), toggle(), listening, busy }
//     options.lang                BCP-47 tag or function returning one, default: document language or the browser's
//     options.speech              "auto" | "native" | "backend", or a function returning one
//     options.transcriber         per-instance override of the global transcriber (or a function returning it)
//     options.onResult(text, isFinal, source)   interim (native only) and final transcript chunks
//     options.onState(listening)        fired when listening/recording starts/stops
//     options.onStatus(status)          "recording" | "transcribing" | "idle" (for live-region announcements)
//     options.onError(code, source)     SpeechRecognition error code, e.g. "not-allowed"; backend adds
//                                       "not-allowed" (getUserMedia denied), "audio-capture",
//                                       "transcribe-failed" (transcriber rejected), "no-speech" (empty text)

const Ctor = () => window.SpeechRecognition || window.webkitSpeechRecognition;

let globalTranscriber = null;

export const setTranscriber = (fn) => { globalTranscriber = typeof fn === 'function' ? fn : null; };
export const getTranscriber = () => globalTranscriber;

const backendAvailable = (t) =>
  !!(t || globalTranscriber) && !!navigator.mediaDevices?.getUserMedia && typeof window.MediaRecorder === 'function';

export function speechSource(mode = 'auto', transcriber) {
  const native = !!Ctor();
  if (mode === 'native') return native ? 'native' : null;
  if (mode === 'backend') return backendAvailable(transcriber) ? 'backend' : null;
  if (native) return 'native';
  return backendAvailable(transcriber) ? 'backend' : null;
}

export const speechSupported = (mode, transcriber) => speechSource(mode, transcriber) !== null;

const pickMime = () => {
  for (const m of ['audio/webm;codecs=opus', 'audio/mp4', 'audio/webm', 'audio/ogg;codecs=opus']) {
    if (window.MediaRecorder.isTypeSupported?.(m)) return m;
  }
  return '';
};

export function createDictation({ lang, speech, transcriber, onResult, onState, onStatus, onError } = {}) {
  let rec = null;
  let recorder = null;
  let stream = null;
  let listening = false;
  let busy = false;
  let starting = false;
  const val = (v) => (typeof v === 'function' ? v() : v);

  const setListening = (v) => {
    if (listening === v) return;
    listening = v;
    onState?.(v);
  };
  const resolveLang = () => val(lang) || document.documentElement.lang || navigator.language || 'en-US';

  const startNative = () => {
    const SR = Ctor();
    rec = new SR();
    rec.lang = resolveLang();
    rec.interimResults = true;
    rec.continuous = false;
    rec.onstart = () => { setListening(true); onStatus?.('recording'); };
    rec.onend = () => { setListening(false); onStatus?.('idle'); rec = null; };
    rec.onerror = (e) => onError?.(e.error, 'native');
    rec.onresult = (e) => {
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i];
        onResult?.(r[0].transcript.trim(), r.isFinal, 'native');
      }
    };
    try { rec.start(); } catch (err) { onError?.(String(err), 'native'); }
  };

  const release = () => { stream?.getTracks().forEach((t) => t.stop()); stream = null; };

  const startBackend = async (fn) => {
    starting = true;
    try {
      try {
        stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      } catch (err) {
        const denied = err?.name === 'NotAllowedError' || err?.name === 'SecurityError';
        onError?.(denied ? 'not-allowed' : 'audio-capture', 'backend');
        return;
      }
      const mime = pickMime();
      const chunks = [];
      try {
        recorder = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
      } catch (err) {
        release();
        onError?.('audio-capture', 'backend');
        return;
      }
      const thisLang = resolveLang();
      recorder.ondataavailable = (e) => { if (e.data?.size) chunks.push(e.data); };
      recorder.onerror = () => onError?.('audio-capture', 'backend');
      recorder.onstop = async () => {
        const type = recorder?.mimeType || mime || chunks[0]?.type || 'audio/webm';
        recorder = null;
        release();
        setListening(false);
        if (!chunks.length) { onStatus?.('idle'); return; }
        const blob = new Blob(chunks, { type });
        busy = true;
        onStatus?.('transcribing');
        try {
          const text = String((await fn(blob, { mime: type, lang: thisLang })) ?? '').trim();
          if (text) onResult?.(text, true, 'backend');
          else onError?.('no-speech', 'backend');
        } catch {
          onError?.('transcribe-failed', 'backend');
        } finally {
          busy = false;
          onStatus?.('idle');
        }
      };
      recorder.start();
      setListening(true);
      onStatus?.('recording');
    } finally {
      starting = false;
    }
  };

  const start = () => {
    if (listening || busy || starting) return;
    const fn = val(transcriber) || globalTranscriber;
    const source = speechSource(val(speech) || 'auto', fn);
    if (source === 'native') startNative();
    else if (source === 'backend') startBackend(fn);
  };

  const stop = () => {
    try { rec?.stop(); } catch { /* already stopped */ }
    try { if (recorder?.state === 'recording') recorder.stop(); } catch { /* already stopped */ }
  };

  return {
    start,
    stop,
    toggle: () => (listening ? stop() : start()),
    get listening() { return listening; },
    get busy() { return busy; },
  };
}
