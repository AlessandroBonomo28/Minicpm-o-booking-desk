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
    date: '', time: '', detail: '',
    lastHash: null,
    pendingFrame: null,     // base64 JPEG da allegare al prossimo chunk
    framesSent: 0,
    lastFrameAt: null,      // per misurare la reazione
    fingerprint() { return `${this.state}|${this.date}|${this.time}|${this.detail}`; },
};
const canvas = $('hud'), ctx = canvas.getContext('2d');

function drawHud() {
    const W = canvas.width, H = canvas.height;
    const theme = {
        IDLE:     { bg: '#263238', fg: '#eceff1', title: 'BOOKING DESK', line1: 'waiting for a request', line2: '' },
        CHECKING: { bg: '#f9a825', fg: '#1a1a1a', title: 'CHECKING...', line1: `${hud.date} ${hud.time || 'ALL DAY'}`, line2: 'please wait' },
        OK:       { bg: '#2e7d32', fg: '#ffffff', title: 'RESULT', line1: `${hud.date} ${hud.time || 'ALL DAY'}`, line2: 'AVAILABLE', line3: hud.detail },
        PARTIAL:  { bg: '#ef6c00', fg: '#ffffff', title: 'RESULT', line1: `${hud.date} ${hud.time || 'ALL DAY'}`, line2: 'PARTLY BOOKED', line3: hud.detail },
        NO:       { bg: '#c62828', fg: '#ffffff', title: 'RESULT', line1: `${hud.date} ${hud.time || 'ALL DAY'}`, line2: 'BOOKED ' + (hud.detail || '').toUpperCase(), line3: '' },
        ERR:      { bg: '#b71c1c', fg: '#ffffff', title: 'ERROR / TIMEOUT', line1: `${hud.date} ${hud.time || 'ALL DAY'}`, line2: 'check failed' },
    }[hud.state];
    ctx.fillStyle = theme.bg; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = theme.fg; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.font = 'bold 34px system-ui, sans-serif'; ctx.fillText(theme.title, W / 2, H * 0.28);
    ctx.font = 'bold 44px system-ui, sans-serif'; ctx.fillText(theme.line1, W / 2, H * 0.50);
    ctx.font = (theme.line2.length > 12 ? 'bold 40px' : 'bold 56px') + ' system-ui, sans-serif'; ctx.fillText(theme.line2, W / 2, H * 0.68);
    if (theme.line3) { ctx.font = 'bold 22px system-ui, sans-serif'; ctx.fillText(String(theme.line3).toUpperCase().slice(0, 40), W / 2, H * 0.82); }
    ctx.font = '18px system-ui, sans-serif'; ctx.globalAlpha = 0.7; ctx.fillText('operator screen', W / 2, H * 0.92); ctx.globalAlpha = 1;
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
    fetch('/api/hud_db/hud_state', { method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ state: hud.state, date: hud.date, time: hud.time }) }).catch(() => {});
}

// simulatore del backend: IN CORSO → (ritardo) → esito
let queryTimer = null;
function startQuery(reason) {
    if (hud.state === 'CHECKING') return;
    const date = $('qDate').value.trim().toUpperCase(), time = $('qTime').value.trim();   // time vuoto = ALL DAY
    const delay = Math.max(0, parseFloat($('qDelay').value) || 0);
    const outcome = $('qOutcome').value;
    hud.detail = '';
    hudLog('sys', `verifica avviata (${reason}): ${date} ${time || 'ALL DAY'}, esito tra ${delay}s`);
    micRing.length = 0;
    setHud('CHECKING', date, time);
    clearTimeout(queryTimer);
    // la verifica passa dal "gestionale" del server (prenotazioni inserite in /static/hud/db.html)
    const t0q = performance.now();
    const pending = fetch('/api/hud_db/check', { method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ date, time, outcome, source: reason, delay_s: delay }) })
        .then(r => r.json()).catch(e => ({ status: 'error', error: e.message }));
    queryTimer = setTimeout(async () => {
        const res = await pending;
        const st = res.status === 'booked' ? 'NO' : res.status === 'available' ? 'OK' : res.status === 'partial' ? 'PARTIAL' : 'ERR';
        hud.detail = res.detail || '';
        setHud(st);
        hudLog('sys', `gestionale ha risposto: ${res.status}${res.name ? ' (' + res.name + ')' : ''} per ${res.date || date} ${res.time || time}` + (res.error ? ' — ' + res.error : ''));
    }, Math.max(0, delay * 1000 - (performance.now() - t0q)));
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
        this.node.port.onmessage = (e) => { if (e.data.type === 'chunk' && !e.data.final) this.onChunk(e.data.audio); };
        src.connect(this.node);
        // tiene vivo il grafo audio (il worklet gira solo se collegato a un'uscita); guadagno 0 = niente eco
        this.sink = this.ctx.createGain(); this.sink.gain.value = 0;
        this.node.connect(this.sink); this.sink.connect(this.ctx.destination);
        // il worklet accumula SOLO dopo il comando start (bug del primo test: zero chunk inviati)
        this.node.port.postMessage({ command: 'start' });
    }
    stop() {
        try { this.node && this.node.port.postMessage({ command: 'stop' }); } catch (_) {}
        try { this.node && this.node.disconnect(); } catch (_) {}
        try { this.stream && this.stream.getTracks().forEach(t => t.stop()); } catch (_) {}
        try { this.ctx && this.ctx.close(); } catch (_) {}
    }
}

// ------------------------------------------------------------------ sessione
let session = null, mic = null, running = false, awaitingReaction = false;

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
    $('btnQuery').disabled = !on; $('btnReset').disabled = !on; $('btnFrame').disabled = !on;
    $('lamp').className = 'lamp' + (on ? ' on' : ''); $('stateText').textContent = on ? 'sessione attiva' : 'disconnesso';
}

async function startSession() {
    $('conv').innerHTML = ''; $('hudLog').innerHTML = '';
    hud.lastHash = null; hud.pendingFrame = null; hud.framesSent = 0; hud.lastFrameAt = null; awaitingReaction = false;
    setHud('IDLE', '', '');
    hud.pendingFrame = null; hud.lastHash = null;   // il frame iniziale lo decide la spunta
    t0ms.v = performance.now();
    transcript.length = 0; lastDecidedText = ''; micRing.length = 0;

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
                micRing.push(new Float32Array(audioF32)); if (micRing.length > MIC_RING_SEC) micRing.shift();
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
    const mode = $('trigMode').value;
    if (mode === 'regex' && hud.state === 'IDLE' && text !== lastSeenText) {
        let re = null;
        try { re = new RegExp($('autoRegex').value, 'i'); } catch (_) {}
        if (re && re.test(text)) startQuery('regex: il modello ha detto "' + (text.match(re) || [''])[0] + '"');
    }
    if (mode === 'tool' && hud.state !== 'CHECKING') scheduleToolDecision(text);
    lastSeenText = text;
}

// ---- modello SEPARATO di tool calling: legge la trascrizione e decide la chiamata
const transcript = [];          // [{role:'assistant'|'user', text}]
const MIC_RING_SEC = 12;        // ultimi secondi di microfono da far trascrivere al tool agent
const micRing = [];
function micRingB64() {
    if (!micRing.length) return null;
    const n = micRing.reduce((a, c) => a + c.length, 0); const out = new Float32Array(n); let o = 0;
    for (const c of micRing) { out.set(c, o); o += c.length; }
    return arrayBufferToBase64(out.buffer);
}
let toolTimer = null, toolBusy = false, lastDecidedText = '';
function noteAssistantText(text) {
    if (!text) return;
    if (transcript.length && transcript[transcript.length - 1].role === 'assistant') transcript[transcript.length - 1].text = text;
    else transcript.push({ role: 'assistant', text });
    if (transcript.length > 8) transcript.shift();
}
function scheduleToolDecision(text) {
    noteAssistantText(text);
    clearTimeout(toolTimer);
    // aspetta che il testo del turno si assesti (~1.2 s senza nuovi delta), poi chiede al modello separato
    toolTimer = setTimeout(() => askToolAgent(text), 1200);
}
async function askToolAgent(text) {
    if (toolBusy || hud.state === 'CHECKING' || text === lastDecidedText || (text || '').length < 8) return;
    toolBusy = true; lastDecidedText = text;
    try {
        const t0 = performance.now();
        const r = await fetch('/api/tool_agent/decide', { method: 'POST', headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ transcript, user_audio_b64: micRingB64(), language: 'en' }) });
        const d = await r.json();
        const dt = ((performance.now() - t0) / 1000).toFixed(1);
        if (!r.ok) { hudLog('warn', `tool agent: ${d.error || r.status}`); return; }
        if (d.user_text) conv('sys', 'TU (ASR): ' + d.user_text);
        const calls = d.tool_calls || [];
        if (!calls.length) { hudLog('sys', `tool agent (${dt}s): nessuna azione — "${(d.raw || '').slice(0, 60)}"`); return; }
        for (const c of calls) {
            hudLog('hud', `TOOL AGENT (${dt}s): ${c.name}(${JSON.stringify(c.arguments)})`);
            if (c.name === 'check_availability' && hud.state !== 'CHECKING') {
                const a = c.arguments || {};
                if (a.date) $('qDate').value = String(a.date);
                $('qTime').value = a.time ? String(a.time) : '';   // niente ora = giornata intera
                startQuery('modello separato');
            }
        }
    } catch (e) { hudLog('warn', 'tool agent errore: ' + e.message); }
    finally { toolBusy = false; }
}
async function checkToolAgent() {
    try {
        const r = await fetch('/api/tool_agent/decide', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ transcript: [] }) });
        $('toolAgentState').textContent = r.ok ? 'tool agent: pronto' : 'tool agent: non raggiungibile';
    } catch (_) { $('toolAgentState').textContent = 'tool agent: non raggiungibile'; }
}

// ------------------------------------------------------------------ UI
$('btnStart').onclick = startSession;
$('btnStop').onclick = stopSession;
$('btnForceListen').onclick = () => session && session.toggleForceListen();
$('btnQuery').onclick = () => startQuery('manuale');
$('btnReset').onclick = () => { clearTimeout(queryTimer); setHud('IDLE', '', ''); };
$('btnFrame').onclick = () => hudSync(true);
drawHud();
checkToolAgent();
