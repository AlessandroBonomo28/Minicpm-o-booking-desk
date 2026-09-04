/**
 * HUD — ramo sperimentale: il frame visivo come segnale di evento asincrono.
 *
 * Idea: il modello (MiniCPM-o 4.5, modalità Omni) riceve il microfono ogni secondo e,
 * SOLO quando lo "schermo dell'operatore" cambia stato, un fotogramma dello schermo.
 * Il fotogramma non trasporta istruzioni per il modello: mostra lo STATO del gestionale.
 *
 * 04/09: macchina a stati della prenotazione (plan/ramo-hud.md). La FSM vive nel gateway
 * (/api/hud_fsm/*); il modello separato (Qwen3-1.7B) estrae soltanto cio' che l'utente ha
 * detto nella battuta appena chiusa dal VAD; questa pagina disegna lo stato e lo manda come
 * frame con il chunk audio successivo. Nessuna modifica al backend.
 */
import { RealtimeSession } from '../duplex/lib/realtime-session.js';
import { arrayBufferToBase64 } from '../duplex/lib/duplex-utils.js';

const SR_IN = 16000, SR_OUT = 24000;
const $ = (id) => document.getElementById(id);

// ------------------------------------------------------------------ log
const t0ms = { v: 0 };
const now = () => t0ms.v ? ((performance.now() - t0ms.v) / 1000) : 0;
function logTo(el, cls, text) {
    const d = document.createElement('div'); d.className = cls;
    d.innerHTML = `<span class="t">${now().toFixed(1)}s</span>`;
    d.appendChild(document.createTextNode(text));
    el.appendChild(d); el.scrollTop = el.scrollHeight; return d;
}
const conv = (cls, t) => logTo($('conv'), cls, t);
const hudLog = (cls, t) => logTo($('hudLog'), cls, t);

// ------------------------------------------------------------------ HUD (schermo) = stato della FSM
const IDLE_FSM = () => ({ state: 'IDLE', intent: null, slots: { month: '', day: '', time: '', date: '' }, missing: [], status: null, detail: '', note: '' });
const hud = {
    fsm: IDLE_FSM(),
    screen: 'IDLE',         // IDLE | COLLECTING | CHECKING | RESULT  (CHECKING: solo lato pagina, con ritardo simulato > 0)
    lastHash: null,
    pendingFrame: null,     // base64 JPEG da allegare al prossimo chunk
    framesSent: 0,
    lastFrameAt: null,      // per misurare la reazione
    fingerprint() {
        const f = this.fsm;
        // un valore respinto e' un evento: entra nell'impronta con il numero di sequenza, cosi' produce un frame anche se
        // lo schermo e' uguale a prima (il frame e' il clock: "April" due volte -> due frame)
        const rej = Object.keys(f.rejected || {}).length ? `|rej${f.seq || 0}:${JSON.stringify(f.rejected)}` : '';
        return `${this.screen}|${f.intent}|${f.slots.month || ''}|${f.slots.day || ''}|${f.slots.time}|${(f.missing || []).join(',')}|${f.status}|${f.detail}|${f.note}${rej}`;
    },
};
const canvas = $('hud'), ctx = canvas.getContext('2d');

const timeLabel = (t) => (!t || t === 'all-day') ? 'ALL DAY' : String(t).toUpperCase();
const slotLine = (f) => `${(f.slots.date || '').toUpperCase()} ${timeLabel(f.slots.time)}`.trim();

/** Tabella "formato del frame per stato" di plan/ramo-hud.md. */
function themeFor() {
    const f = hud.fsm;
    switch (hud.screen) {
        case 'COLLECTING': {
            // campi indipendenti: si mostra quello che c'e' ('APRIL ?' / '? 2' / 'APRIL 2') e il primo che manca
            const miss = (f.missing || [])[0] || '';
            const month = (f.slots.month || '').toUpperCase(), day = f.slots.day || '';
            const rejKeys = Object.keys(f.rejected || {});
            const dateLine = (month || day) ? `DATE: ${month || '?'} ${day || '?'}` : 'DATE: ?';
            let line3 = (f.slots.time && miss !== 'time') ? `TIME: ${timeLabel(f.slots.time)}` : '';
            if (rejKeys.length) line3 = `"${String(f.rejected[rejKeys[0]]).toUpperCase()}" NOT VALID`;
            return { bg: '#1565c0', fg: '#ffffff', title: f.intent === 'check' ? 'AVAILABILITY CHECK' : 'NEW BOOKING',
                     line1: dateLine, line2: `MISSING: ${miss.toUpperCase()}`, line3 };
        }
        case 'CHECKING':
            return { bg: '#f9a825', fg: '#1a1a1a', title: 'CHECKING...', line1: slotLine(f), line2: 'please wait', line3: '' };
        case 'RESULT': {
            const s = f.status, d = (f.detail || '').toUpperCase();
            if (s === 'error') return { bg: '#b71c1c', fg: '#ffffff', title: 'ERROR / TIMEOUT', line1: slotLine(f), line2: f.intent === 'book' ? 'request failed' : 'check failed', line3: '' };
            if (f.intent === 'book') {
                if (s === 'confirmed') return { bg: '#2e7d32', fg: '#ffffff', title: 'BOOKING DONE', line1: slotLine(f), line2: 'CONFIRMED', line3: '' };
                return { bg: '#c62828', fg: '#ffffff', title: 'BOOKING', line1: slotLine(f), line2: 'SLOT TAKEN', line3: d ? 'BOOKED ' + d : '' };
            }
            if (s === 'available') return { bg: '#2e7d32', fg: '#ffffff', title: 'RESULT', line1: slotLine(f), line2: 'AVAILABLE', line3: d };
            if (s === 'partial') return { bg: '#ef6c00', fg: '#ffffff', title: 'RESULT', line1: slotLine(f), line2: 'PARTLY BOOKED', line3: d };
            return { bg: '#c62828', fg: '#ffffff', title: 'RESULT', line1: slotLine(f), line2: 'ALREADY BOOKED', line3: d };
        }
        default:
            return { bg: '#263238', fg: '#eceff1', title: 'BOOKING DESK', line1: 'waiting for a request', line2: f.note || '', line3: '' };
    }
}

function drawHud() {
    const W = canvas.width, H = canvas.height, theme = themeFor();
    ctx.fillStyle = theme.bg; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = theme.fg; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.font = 'bold 34px system-ui, sans-serif'; ctx.fillText(theme.title, W / 2, H * 0.28);
    ctx.font = 'bold 44px system-ui, sans-serif'; ctx.fillText(theme.line1, W / 2, H * 0.50);
    ctx.font = (theme.line2.length > 12 ? 'bold 40px' : 'bold 56px') + ' system-ui, sans-serif'; ctx.fillText(theme.line2, W / 2, H * 0.68);
    if (theme.line3) { ctx.font = 'bold 22px system-ui, sans-serif'; ctx.fillText(String(theme.line3).slice(0, 40), W / 2, H * 0.82); }
    ctx.font = '18px system-ui, sans-serif'; ctx.globalAlpha = 0.7; ctx.fillText('operator screen', W / 2, H * 0.92); ctx.globalAlpha = 1;
    $('hudState').textContent = hud.screen + (hud.fsm.status ? ' ' + hud.fsm.status.toUpperCase() : '') + ((hud.fsm.missing || []).length ? ' (missing ' + hud.fsm.missing.join(',') + ')' : '');
}

/** Gate sul cambio: produce un frame SOLO se lo stato e' cambiato dall'ultimo frame inviato. */
function hudSync(force = false) {
    drawHud();
    const h = hud.fingerprint();
    if (!force && h === hud.lastHash) return;
    hud.lastHash = h;
    hud.pendingFrame = canvas.toDataURL('image/jpeg', 0.85).split(',')[1];
    hudLog('hud', `frame pronto (${$('hudState').textContent}) → allegato al prossimo chunk audio`);
}

/** Etichetta per db.html (pill): IDLE / COLLECTING / CHECKING / OK / PARTIAL / NO / ERR. */
function screenLabel() {
    const f = hud.fsm;
    if (hud.screen !== 'RESULT') return hud.screen;
    if (f.status === 'error') return 'ERR';
    if (f.status === 'available' || f.status === 'confirmed') return 'OK';
    if (f.status === 'partial') return 'PARTIAL';
    return 'NO';
}

function syncScreen() {
    hudSync();
    fetch('/api/hud_db/hud_state', { method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ state: screenLabel(), date: hud.fsm.slots.date, time: hud.fsm.slots.time }) }).catch(() => {});
}

// applica uno stato della FSM (dal gateway) allo schermo; con ritardo simulato > 0 il RESULT passa da CHECKING
let queryTimer = null;
function applyFsm(fsm, delay = 0) {
    clearTimeout(queryTimer);
    fsm = Object.assign(IDLE_FSM(), fsm || {}); fsm.slots = Object.assign({ month: '', day: '', time: '', date: '' }, fsm.slots || {});
    const changed = JSON.stringify(fsm) !== JSON.stringify(hud.fsm);
    hud.fsm = fsm;
    if (fsm.state === 'RESULT' && delay > 0 && changed) {
        hud.screen = 'CHECKING'; syncScreen();
        queryTimer = setTimeout(() => { hud.screen = 'RESULT'; syncScreen(); hudLog('sys', `esito mostrato dopo ${delay}s: ${fsm.status}${fsm.detail ? ' (' + fsm.detail + ')' : ''}`); }, delay * 1000);
    } else {
        hud.screen = fsm.state; syncScreen();
    }
}

async function fsmEvent(toolCalls, userText, source) {
    const delay = Math.max(0, parseFloat($('qDelay').value) || 0);
    const r = await fetch('/api/hud_fsm/event', { method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ tool_calls: toolCalls, user_text: userText || '', outcome: $('qOutcome').value, source, delay_s: delay }) });
    const d = await r.json();
    if (!r.ok) { hudLog('warn', 'FSM: ' + (d.error || r.status)); return null; }
    const f = d.fsm;
    hudLog(d.changed ? 'hud' : 'sys', `FSM → ${f.state}${f.intent ? ' ' + f.intent : ''} ${f.slots.month || '?'} ${f.slots.day || '?'} ${f.slots.time || ''}` +
        ((f.missing || []).length ? ' · manca ' + f.missing.join(', ') : '') +
        (Object.keys(f.rejected || {}).length ? ' · NON CAPITO ' + Object.entries(f.rejected).map(([k, v]) => `${k}="${v}"`).join(' ') : '') + (f.status ? ' · ' + f.status : '') + (f.detail ? ' (' + f.detail + ')' : '') + (f.note ? ' · ' + f.note : '') + (d.changed ? '' : ' · invariato'));
    applyFsm(f, delay);
    return f;
}

async function fsmReset() {
    clearTimeout(queryTimer);
    try {
        const r = await fetch('/api/hud_fsm/reset', { method: 'POST' });
        applyFsm(await r.json(), 0);
    } catch (_) { applyFsm(IDLE_FSM(), 0); }
}

// richiesta manuale dal pannello (senza voce): check o book con data/ora scritte
function manualRequest() {
    const intent = $('qIntent').value, date = $('qDate').value.trim(), time = $('qTime').value.trim();
    const args = {}; if (date) args.date = date; if (time) args.time = time;
    hudLog('sys', `richiesta manuale: ${intent}(${JSON.stringify(args)})`);
    fsmEvent([{ name: intent, arguments: args }], '', 'manuale').catch(e => hudLog('warn', 'FSM errore: ' + e.message));
}

// ------------------------------------------------------------------ microfono + VAD
/** VAD a energia, risoluzione 100 ms: parli -> accumula; taci per `silenceMs` -> fine turno (callback con l'audio della battuta). */
class TurnDetector {
    constructor(onTurnEnd) {
        this.onTurnEnd = onTurnEnd; this.speaking = false; this.speechMs = 0; this.silenceMs = 0; this.frames = []; this.preroll = [];
    }
    params() {
        return { thr: parseFloat($('vadThr').value) || 0.02, silence: parseInt($('vadSilence').value, 10) || 600, minSpeech: parseInt($('vadMin').value, 10) || 300 };
    }
    feed(frame) {   // frame = Float32Array da 100 ms
        const { thr, silence, minSpeech } = this.params();
        let e = 0; for (let i = 0; i < frame.length; i++) e += frame[i] * frame[i]; const rms = Math.sqrt(e / frame.length);
        $('vadMeter').textContent = rms.toFixed(3); $('vadState').textContent = this.speaking ? 'PARLI' : 'silenzio';
        if (!this.speaking) {
            this.preroll.push(frame); if (this.preroll.length > 3) this.preroll.shift();   // 300 ms prima dell'attacco
            if (rms > thr) { this.speaking = true; this.speechMs = 100; this.silenceMs = 0; this.frames = this.preroll.slice(); this.frames.push(frame); }
            return;
        }
        this.frames.push(frame);
        if (rms > thr) { this.speechMs += 100; this.silenceMs = 0; }
        else { this.silenceMs += 100; }
        if (this.silenceMs >= silence) {
            const spoke = this.speechMs >= minSpeech; const frames = this.frames;
            this.speaking = false; this.frames = []; this.preroll = []; this.speechMs = 0; this.silenceMs = 0;
            if (spoke) {
                const n = frames.reduce((a, f) => a + f.length, 0); const out = new Float32Array(n); let o = 0;
                for (const f of frames) { out.set(f, o); o += f.length; }
                this.onTurnEnd(out);
            }
        }
    }
}

class MicCapture {
    constructor(onChunk, onFrame100) { this.onChunk = onChunk; this.onFrame100 = onFrame100; this.ctx = null; this.stream = null; this.node = null; this.vadNode = null; }
    async start() {
        this.stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 }, video: false });
        this.ctx = new AudioContext({ sampleRate: SR_IN });
        if (this.ctx.state === 'suspended') await this.ctx.resume();
        await this.ctx.audioWorklet.addModule('/static/duplex/lib/capture-processor.js');
        const src = this.ctx.createMediaStreamSource(this.stream);
        this.node = new AudioWorkletNode(this.ctx, 'capture-processor', { processorOptions: { chunkSize: SR_IN } });
        this.node.port.onmessage = (e) => { if (e.data.type === 'chunk' && !e.data.final) this.onChunk(e.data.audio); };
        src.connect(this.node);
        // secondo nodo: fettine da 100 ms per il VAD (stesso worklet, chunk piu' corto)
        this.vadNode = new AudioWorkletNode(this.ctx, 'capture-processor', { processorOptions: { chunkSize: SR_IN / 10 } });
        this.vadNode.port.onmessage = (e) => { if (e.data.type === 'chunk' && !e.data.final) this.onFrame100(e.data.audio); };
        src.connect(this.vadNode); this.vadNode.port.postMessage({ command: 'start' });
        // tiene vivo il grafo audio (il worklet gira solo se collegato a un'uscita); guadagno 0 = niente eco
        this.sink = this.ctx.createGain(); this.sink.gain.value = 0;
        this.node.connect(this.sink); this.sink.connect(this.ctx.destination);
        // il worklet accumula SOLO dopo il comando start (bug del primo test: zero chunk inviati)
        this.node.port.postMessage({ command: 'start' });
    }
    stop() {
        try { this.node && this.node.port.postMessage({ command: 'stop' }); } catch (_) {}
        try { this.vadNode && this.vadNode.port.postMessage({ command: 'stop' }); this.vadNode && this.vadNode.disconnect(); } catch (_) {}
        try { this.node && this.node.disconnect(); } catch (_) {}
        try { this.stream && this.stream.getTracks().forEach(t => t.stop()); } catch (_) {}
        try { this.ctx && this.ctx.close(); } catch (_) {}
    }
}

// ------------------------------------------------------------------ sessione
let session = null, mic = null, running = false, awaitingReaction = false, lastWindowEvents = 0;
let lastMetrics = {}, lastModelState = '';

/** Riga di stato compatta nella conversazione (dopo ogni turno), per rileggere i test dal log incollato. */
function stateLine(tag) {
    const m = lastMetrics, w = m.windowStats || {}, f = hud.fsm;
    const win = w.mode ? `${w.mode} ${w.high}/${w.low} scorr ${w.events ?? 0} scartati ${w.dropped_tokens ?? 0}` : '?';
    const fsm = `${f.state}${f.intent ? ' ' + f.intent : ''}${(f.slots.month || f.slots.day) ? ' ' + (f.slots.month || '?') + ' ' + (f.slots.day || '?') : ''}${f.slots.time ? ' ' + f.slots.time : ''}` +
        ((f.missing || []).length ? ' manca ' + f.missing.join(',') : '') + (f.status ? ' ' + f.status : '') + (f.note ? ' ' + f.note : '');
    return `STATO [${tag}] KV ${m.kvCacheLength ?? '?'} · finestra ${win} · FSM ${fsm} · lp ${$('lengthPenalty').value} trp ${$('textRepPenalty').value}`;
}

async function loadRefAudio() {
    const choice = $('refChoice').value;
    if (choice === 'none') return null;
    const id = choice === 'italiano' ? 'italiano' : 'english_call';
    try {
        const r = await fetch(`/api/presets/audio_duplex/${id}/audio`);
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const d = await r.json();
        const ra = d.ref_audio || {};
        return ra.data || d.ref_audio_base64 || null;
    } catch (e) { conv('warn', 'voce di riferimento non caricata: ' + e.message); return null; }
}

function setRunning(on) {
    running = on;
    $('btnStart').disabled = on; $('btnStop').disabled = !on; $('btnForceListen').disabled = !on;
    $('btnFrame').disabled = !on;
    $('lamp').className = 'lamp' + (on ? ' on' : ''); $('stateText').textContent = on ? 'sessione attiva' : 'disconnesso';
}

let starting = false;
async function startSession() {
    // una pagina = una sessione: il 04/09 tre click su "Avvia" hanno aperto tre websocket (2 in coda) e il
    // microfono spediva i chunk a quello in coda -> il backend non ha mai ricevuto audio
    if (running || starting) return;
    starting = true; $('btnStart').disabled = true;
    try { await startSessionInner(); }
    finally { starting = false; if (!running) $('btnStart').disabled = false; }
}

async function startSessionInner() {
    $('conv').innerHTML = ''; $('hudLog').innerHTML = '';
    hud.lastHash = null; hud.pendingFrame = null; hud.framesSent = 0; hud.lastFrameAt = null; awaitingReaction = false;
    await fsmReset();                                // ogni sessione parte da IDLE (le prenotazioni in db.html restano)
    hud.pendingFrame = null; hud.lastHash = null;   // il frame iniziale lo decide la spunta
    t0ms.v = performance.now();
    userLines.length = 0;

    session = new RealtimeSession('hud', {
        getMaxKvTokens: () => 8192,
        getPlaybackDelayMs: () => parseInt($('playbackDelay').value, 10) || 600,
        outputSampleRate: SR_OUT,
        getWsUrl: () => {
            const proto = location.protocol === 'https:' ? 'wss' : 'ws';
            const url = `${proto}://${location.host}/v1/realtime?mode=video`;
            return window.ClientIdentity ? window.ClientIdentity.appendToUrl(url) : url;
        },
    });
    session.onSystemLog = (t) => conv('sys', t);
    session.onSpeakStart = (text) => {
        const el = conv('ai', 'AI: ' + (text || ''));
        el.dataset.prefix = 'AI: ';
        onModelText(text || '');
        return el;
    };
    session.onSpeakUpdate = (el, text) => { if (el) { el.textContent = ''; el.innerHTML = `<span class="t">${now().toFixed(1)}s</span>`; el.appendChild(document.createTextNode('AI: ' + text)); } onModelText(text || ''); };
    session.onSpeakEnd = () => {};
    session.onListenResult = (r) => { if (r && r.text) conv('sys', 'utente: ' + r.text); };
    session.onMetrics = (d) => {
        if (!d) return;
        if (d.sessionState) $('stateText').textContent = d.sessionState;
        if (d.kvCacheLength !== undefined) lastMetrics = d;
        if (d.modelState && d.modelState !== lastModelState) {
            if (d.modelState === 'end_of_turn') conv('sys', stateLine('fine turno AI'));
            lastModelState = d.modelState;
        }
        if (d.kvCacheLength !== undefined) {
            const w = d.windowStats || {};
            const win = w.mode ? `${w.mode}${w.enabled ? '' : ' (spenta)'} ${w.high}/${w.low} · scorrimenti ${w.events ?? 0} · scartati ${w.dropped_tokens ?? 0} tok (${w.dropped_units ?? 0} unità)` : '?';
            $('kvInfo').textContent = `KV: ${d.kvCacheLength} token · finestra: ${win}`;
            if (w.events !== undefined && w.events > lastWindowEvents) {
                lastWindowEvents = w.events;
                conv('sys', `FINESTRA KV: scorrimento #${w.events} — scartate ${w.dropped_units} unità (${w.dropped_tokens} token), KV ora ${d.kvCacheLength}`);
            }
        }
    };
    session.onForceListenChange = (a) => { $('btnForceListen').style.background = a ? '#ffe0b2' : '#fff'; };

    const preparePayload = { config: { length_penalty: parseFloat($('lengthPenalty').value) || 1.0,
                                       text_repetition_penalty: parseFloat($('textRepPenalty').value) || 1.0,
                                       sliding_window_mode: $('slidingWindow').value, sliding_window_high_tokens: 4000, sliding_window_low_tokens: 3500 },
                             use_tts: true, max_slice_nums: 1 };
    lastWindowEvents = 0; lastMetrics = {}; lastModelState = ''; $('kvInfo').textContent = 'KV: — · finestra: ' + $('slidingWindow').value;
    const ref = await loadRefAudio();
    if (ref) preparePayload.ref_audio_base64 = ref;

    const sess = session;   // il microfono spedisce SOLO alla sessione per cui e' stato creato
    try {
        await sess.start($('systemPrompt').value, preparePayload, async () => {
            if ($('sendInitial').checked) hudSync(true);
            const turns = new TurnDetector((utterance) => onUserTurnEnd(utterance));
            mic = new MicCapture((audioF32) => {
                const msg = { type: 'audio_chunk', audio_base64: arrayBufferToBase64(audioF32.buffer) };
                if (hud.pendingFrame) {
                    msg.frame_base64_list = [hud.pendingFrame];
                    hud.pendingFrame = null; hud.framesSent++; hud.lastFrameAt = now(); awaitingReaction = true;
                    $('framesSent').textContent = hud.framesSent;
                    $('frameInfo').textContent = `ultimo frame inviato a ${hud.lastFrameAt.toFixed(1)}s (${$('hudState').textContent})`;
                    hudLog('hud', `FRAME INVIATO (${$('hudState').textContent}) con il chunk #${sess.chunksSent + 1}`);
                }
                sess.sendChunk(msg);
                $('chunks').textContent = sess.chunksSent;
            }, (frame100) => turns.feed(frame100));
            await mic.start();
            conv('sys', 'microfono attivo — parla con lo sportello (VAD attivo: la decisione parte quando finisci di parlare; CUFFIE)');
        });
        setRunning(true);
    } catch (e) {
        conv('warn', 'avvio fallito: ' + (e && e.message ? e.message : e));
        stopSession();
    }
}

function stopSession() {
    clearTimeout(queryTimer);
    try { mic && mic.stop(); } catch (_) {}
    try { session && session.stop(); } catch (_) {}
    mic = null; session = null; setRunning(false);
}

// testo del modello: misura la reazione al frame (solo osservazione: il trigger e' il turno dell'utente)
function onModelText(text) {
    if (!text) return;
    if (awaitingReaction && hud.lastFrameAt !== null) {
        awaitingReaction = false;
        hudLog('hud', `REAZIONE +${(now() - hud.lastFrameAt).toFixed(1)}s dopo il frame (${$('hudState').textContent}): "${text.slice(0, 60)}"`);
    }
}

// ---- estrattore (modello SEPARATO): riceve SOLO le battute dell'utente + lo stato della FSM
const userLines = [];           // ultime battute dell'utente (ASR), contesto per l'estrattore
let toolBusy = false;
const pendingTurns = [];        // battute arrivate mentre l'estrattore era occupato: si accodano, non si scartano

/** Fine del tuo turno: ASR della sola battuta (GPU) + estrazione + evento alla FSM. */
async function onUserTurnEnd(utterance) {
    const secs = (utterance.length / SR_IN).toFixed(1);
    hudLog('sys', `TURNO UTENTE finito (${secs} s di voce)`);
    if ($('trigMode').value !== 'tool') return;
    if (toolBusy) { pendingTurns.push(utterance); if (pendingTurns.length > 2) pendingTurns.shift(); hudLog('sys', `estrattore occupato: battuta in coda (${pendingTurns.length})`); return; }
    toolBusy = true;
    try {
        const t0 = performance.now();
        const transcript = userLines.map(t => ({ role: 'user', text: t }));
        const r = await fetch('/api/tool_agent/decide', { method: 'POST', headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ transcript, user_audio_b64: arrayBufferToBase64(utterance.buffer), language: 'en', fsm: hud.fsm }) });
        const d = await r.json();
        const dt = ((performance.now() - t0) / 1000).toFixed(2);
        if (!r.ok) { hudLog('warn', `estrattore: ${d.error || r.status}`); return; }
        if (d.user_text) { conv('sys', 'TU (ASR): ' + d.user_text); userLines.push(d.user_text); if (userLines.length > 4) userLines.shift(); }
        const calls = d.tool_calls || [];
        const tim = `ASR ${d.asr_s ?? '?'} s + LLM ${d.llm_s ?? '?'} s = ${dt} s`;
        if (!calls.length) { hudLog('sys', `estrattore (${tim}): nessuna azione — "${(d.raw || '').slice(0, 70)}"`); return; }
        for (const c of calls) hudLog('hud', `ESTRATTORE (${tim}): ${c.name}(${JSON.stringify(c.arguments)})`);
        await fsmEvent(calls, d.user_text, 'estrattore (turno utente)');
        conv('sys', stateLine(`dopo la tua battuta: ${calls.map(c => c.name + JSON.stringify(c.arguments)).join(' ')}`));
    } catch (e) { hudLog('warn', 'estrattore errore: ' + e.message); }
    finally { toolBusy = false; if (pendingTurns.length) onUserTurnEnd(pendingTurns.shift()); }
}

async function checkToolAgent() {
    try {
        const r = await fetch('/api/tool_agent/decide', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ transcript: [] }) });
        $('toolAgentState').textContent = r.ok ? 'estrattore: pronto' : 'estrattore: non raggiungibile';
    } catch (_) { $('toolAgentState').textContent = 'estrattore: non raggiungibile'; }
}

// ------------------------------------------------------------------ UI
$('btnStart').onclick = startSession;
$('btnStop').onclick = stopSession;
$('btnForceListen').onclick = () => session && session.toggleForceListen();
$('btnQuery').onclick = manualRequest;
$('btnReset').onclick = fsmReset;
$('btnFrame').onclick = () => hudSync(true);
drawHud();
checkToolAgent();
fetch('/api/hud_fsm').then(r => r.json()).then(f => applyFsm(f, 0)).catch(() => {});   // stato corrente della FSM (db.html lo vede uguale)
