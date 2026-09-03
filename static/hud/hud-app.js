/**
 * HUD — ramo sperimentale: il frame visivo come segnale di evento asincrono.
 *
 * Idea: il modello (MiniCPM-o 4.5, modalità Omni) riceve il microfono ogni secondo e,
 * SOLO quando lo "schermo dell'operatore" cambia stato, un fotogramma dello schermo.
 * Il fotogramma non trasporta dati per il modello: e' il clock che gli dice "ora".
 *
 * Nessuna modifica al backend: si usa il protocollo normale (input.append con
 * audio + video_frames opzionali). Il gate sul cambio e' un hash dello stato HUD.
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

// ------------------------------------------------------------------ HUD (schermo)
const hud = {
    state: 'IDLE',          // IDLE | CHECKING | OK | NO | ERR
    date: '', time: '',
    lastHash: null,
    pendingFrame: null,     // base64 JPEG da allegare al prossimo chunk
    framesSent: 0,
    lastFrameAt: null,      // per misurare la reazione
    fingerprint() { return `${this.state}|${this.date}|${this.time}`; },
};
const canvas = $('hud'), ctx = canvas.getContext('2d');

function drawHud() {
    const W = canvas.width, H = canvas.height;
    const theme = {
        IDLE:     { bg: '#263238', fg: '#eceff1', title: 'SPORTELLO PRENOTAZIONI', line1: 'in attesa di una richiesta', line2: '' },
        CHECKING: { bg: '#f9a825', fg: '#1a1a1a', title: 'VERIFICA IN CORSO...', line1: `${hud.date} ${hud.time}`, line2: 'attendere' },
        OK:       { bg: '#2e7d32', fg: '#ffffff', title: 'RISULTATO', line1: `${hud.date} ${hud.time}`, line2: 'LIBERO' },
        NO:       { bg: '#c62828', fg: '#ffffff', title: 'RISULTATO', line1: `${hud.date} ${hud.time}`, line2: 'OCCUPATO' },
        ERR:      { bg: '#b71c1c', fg: '#ffffff', title: 'ERRORE / TIMEOUT', line1: `${hud.date} ${hud.time}`, line2: 'verifica fallita' },
    }[hud.state];
    ctx.fillStyle = theme.bg; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = theme.fg; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.font = 'bold 34px system-ui, sans-serif'; ctx.fillText(theme.title, W / 2, H * 0.28);
    ctx.font = 'bold 44px system-ui, sans-serif'; ctx.fillText(theme.line1, W / 2, H * 0.50);
    ctx.font = 'bold 56px system-ui, sans-serif'; ctx.fillText(theme.line2, W / 2, H * 0.70);
    ctx.font = '18px system-ui, sans-serif'; ctx.globalAlpha = 0.7; ctx.fillText('schermo operatore', W / 2, H * 0.92); ctx.globalAlpha = 1;
    $('hudState').textContent = hud.state;
}

/** Gate sul cambio: produce un frame SOLO se lo stato e' cambiato dall'ultimo frame inviato. */
function hudSync(force = false) {
    drawHud();
    const h = hud.fingerprint();
    if (!force && h === hud.lastHash) return;
    hud.lastHash = h;
    hud.pendingFrame = canvas.toDataURL('image/jpeg', 0.85).split(',')[1];
    hudLog('hud', `frame pronto (stato ${hud.state}${hud.state !== 'IDLE' ? ' ' + hud.date + ' ' + hud.time : ''}) → allegato al prossimo chunk audio`);
}

function setHud(state, date, time) {
    hud.state = state; if (date !== undefined) hud.date = date; if (time !== undefined) hud.time = time;
    hudSync();
}

// simulatore del backend: IN CORSO → (ritardo) → esito
let queryTimer = null;
function startQuery(reason) {
    if (hud.state === 'CHECKING') return;
    const date = $('qDate').value.trim().toUpperCase(), time = $('qTime').value.trim();
    const delay = Math.max(0, parseFloat($('qDelay').value) || 0);
    const outcome = $('qOutcome').value;
    hudLog('sys', `verifica avviata (${reason}): ${date} ${time}, esito tra ${delay}s`);
    setHud('CHECKING', date, time);
    clearTimeout(queryTimer);
    queryTimer = setTimeout(() => {
        setHud(outcome === 'ok' ? 'OK' : outcome === 'no' ? 'NO' : 'ERR');
        hudLog('sys', `backend ha risposto: ${hud.state}`);
    }, delay * 1000);
}

// ------------------------------------------------------------------ microfono
class MicCapture {
    constructor(onChunk) { this.onChunk = onChunk; this.ctx = null; this.stream = null; this.node = null; }
    async start() {
        this.stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1 }, video: false });
        this.ctx = new AudioContext({ sampleRate: SR_IN });
        if (this.ctx.state === 'suspended') await this.ctx.resume();
        await this.ctx.audioWorklet.addModule('/static/duplex/lib/capture-processor.js');
        const src = this.ctx.createMediaStreamSource(this.stream);
        this.node = new AudioWorkletNode(this.ctx, 'capture-processor', { processorOptions: { chunkSize: SR_IN } });
        this.node.port.onmessage = (e) => { if (e.data.type === 'chunk') this.onChunk(e.data.audio); };
        src.connect(this.node);
    }
    stop() {
        try { this.node && this.node.disconnect(); } catch (_) {}
        try { this.stream && this.stream.getTracks().forEach(t => t.stop()); } catch (_) {}
        try { this.ctx && this.ctx.close(); } catch (_) {}
    }
}

// ------------------------------------------------------------------ sessione
let session = null, mic = null, running = false, awaitingReaction = false;

async function loadRefAudio() {
    if ($('refChoice').value !== 'italiano') return null;
    try {
        const r = await fetch('/api/presets/audio_duplex/italiano/audio');
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const d = await r.json();
        const ra = d.ref_audio || {};
        return ra.data || d.ref_audio_base64 || null;
    } catch (e) { conv('warn', 'voce di riferimento non caricata: ' + e.message); return null; }
}

function setRunning(on) {
    running = on;
    $('btnStart').disabled = on; $('btnStop').disabled = !on; $('btnForceListen').disabled = !on;
    $('btnQuery').disabled = !on; $('btnReset').disabled = !on; $('btnFrame').disabled = !on;
    $('lamp').className = 'lamp' + (on ? ' on' : ''); $('stateText').textContent = on ? 'sessione attiva' : 'disconnesso';
}

async function startSession() {
    $('conv').innerHTML = ''; $('hudLog').innerHTML = '';
    hud.lastHash = null; hud.pendingFrame = null; hud.framesSent = 0; hud.lastFrameAt = null; awaitingReaction = false;
    setHud('IDLE', '', '');
    hud.pendingFrame = null; hud.lastHash = null;   // il frame iniziale lo decide la spunta
    t0ms.v = performance.now();

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
    session.onMetrics = (d) => { if (d && d.sessionState) $('stateText').textContent = d.sessionState; };
    session.onForceListenChange = (a) => { $('btnForceListen').style.background = a ? '#ffe0b2' : '#fff'; };

    const preparePayload = { config: { length_penalty: parseFloat($('lengthPenalty').value) || 1.0 }, use_tts: true, max_slice_nums: 1 };
    const ref = await loadRefAudio();
    if (ref) preparePayload.ref_audio_base64 = ref;

    try {
        await session.start($('systemPrompt').value, preparePayload, async () => {
            if ($('sendInitial').checked) hudSync(true);
            mic = new MicCapture((audioF32) => {
                const msg = { type: 'audio_chunk', audio_base64: arrayBufferToBase64(audioF32.buffer) };
                if (hud.pendingFrame) {
                    msg.frame_base64_list = [hud.pendingFrame];
                    hud.pendingFrame = null; hud.framesSent++; hud.lastFrameAt = now(); awaitingReaction = true;
                    $('framesSent').textContent = hud.framesSent;
                    $('frameInfo').textContent = `ultimo frame inviato a ${hud.lastFrameAt.toFixed(1)}s (stato ${hud.state})`;
                    hudLog('hud', `FRAME INVIATO (stato ${hud.state}) con il chunk #${session.chunksSent + 1}`);
                }
                session.sendChunk(msg);
                $('chunks').textContent = session.chunksSent;
            });
            await mic.start();
            conv('sys', 'microfono attivo — parla con lo sportello');
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

// testo del modello: misura la reazione al frame e auto-trigger della verifica
let lastSeenText = '';
function onModelText(text) {
    if (!text) return;
    if (awaitingReaction && hud.lastFrameAt !== null) {
        awaitingReaction = false;
        hudLog('hud', `REAZIONE +${(now() - hud.lastFrameAt).toFixed(1)}s dopo il frame (stato ${hud.state}): "${text.slice(0, 60)}"`);
    }
    if ($('autoTrig').checked && hud.state === 'IDLE' && text !== lastSeenText) {
        let re = null;
        try { re = new RegExp($('autoRegex').value, 'i'); } catch (_) {}
        if (re && re.test(text)) startQuery('auto: il modello ha detto "' + (text.match(re) || [''])[0] + '"');
    }
    lastSeenText = text;
}

// ------------------------------------------------------------------ UI
$('btnStart').onclick = startSession;
$('btnStop').onclick = stopSession;
$('btnForceListen').onclick = () => session && session.toggleForceListen();
$('btnQuery').onclick = () => startQuery('manuale');
$('btnReset').onclick = () => { clearTimeout(queryTimer); setHud('IDLE', '', ''); };
$('btnFrame').onclick = () => hudSync(true);
drawHud();
