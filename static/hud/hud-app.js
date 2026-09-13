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
// ogni riga dei due log va anche al gateway (logs_demo/hud_runs/<sessione>.log): la run si rilegge senza incollarla
const runLog = { session: 'nosession', queue: [], timer: null };
function runLogPush(el, cls, text) {
    const m = /Session created: (sess_[0-9a-f]+)/.exec(text);
    if (m) runLog.session = m[1];
    if (!runLog.queue.length) runLog.firstAt = performance.now();
    runLog.queue.push({ t: now(), log: el.id === 'conv' ? 'conv' : 'hud', cls, text });
    if (!runLog.timer) runLog.timer = setTimeout(runLogFlush, 1000);
}
function runLogFlush() {
    runLog.timer = null;
    if (!runLog.queue.length) return;
    // prima dell'id di sessione le righe aspettano (max 60 s): CONFIG e i primi frame devono finire nel file della sessione
    if (runLog.session === 'nosession' && performance.now() - runLog.firstAt < 60000) { runLog.timer = setTimeout(runLogFlush, 1000); return; }
    const lines = runLog.queue.splice(0);
    fetch('/api/hud/log', { method: 'POST', headers: { 'content-type': 'application/json' }, keepalive: true,
        body: JSON.stringify({ session: runLog.session, lines }) }).catch(() => {});
}
function logTo(el, cls, text) {
    const d = document.createElement('div'); d.className = cls;
    d.innerHTML = `<span class="t">${now().toFixed(1)}s</span>`;
    d.appendChild(document.createTextNode(text));
    el.appendChild(d); el.scrollTop = el.scrollHeight;
    runLogPush(el, cls, text);
    return d;
}
const conv = (cls, t) => logTo($('conv'), cls, t);
const hudLog = (cls, t) => logTo($('hudLog'), cls, t);

// ------------------------------------------------------------------ HUD (schermo) = stato della FSM
const IDLE_FSM = () => ({ state: 'IDLE', intent: null, slots: { month: '', day: '', time: '', date: '' }, missing: [], status: null, detail: '', note: '' });
const hud = {
    fsm: IDLE_FSM(),
    screen: 'IDLE',         // IDLE | COLLECTING | CHECKING | CONFIRM | DONE  (CHECKING: solo lato pagina, con ritardo simulato > 0)
    lastHash: null,
    pendingFrame: null,     // base64 JPEG da allegare al prossimo chunk
    framesSent: 0,
    lastFrameAt: null,      // per misurare la reazione
    fingerprint() {
        const f = this.fsm;
        // impronta = quello che si VEDE (CONFIRM -> DONE non cambia i pixel: nessun frame nuovo);
        // un valore respinto e' un evento: entra nell'impronta con il numero di sequenza, cosi' produce un frame anche se
        // lo schermo e' uguale a prima (il frame e' il clock: "April" due volte -> due frame)
        const rej = Object.keys(f.rejected || {}).length ? `|rej${f.seq || 0}:${JSON.stringify(f.rejected)}` : '';
        const act = '';   // nessun atto sullo schermo (07/09)
        return JSON.stringify(themeForSeq()) + '|' + act + '|' + (f.level || '') + (f.hint || '') + '|b' + (blinkLeft > 0 ? blinkPhase : '') + rej;
    },
};
const canvas = $('hud'), ctx = canvas.getContext('2d');

/** Orari in forma parlata ('4 PM', '4:30 PM'): l'omni li dice cosi' e non inverte i numeri 24h. */
function timeLabel(t) {
    if (!t || t === 'all-day') return 'ALL DAY';
    const m = /^(\d{1,2}):(\d{2})$/.exec(String(t).trim());
    if (!m) return String(t).toUpperCase();
    const h = parseInt(m[1], 10), mm = m[2], h12 = ((h + 11) % 12) + 1, ap = h < 12 ? 'AM' : 'PM';
    return mm === '00' ? `${h12} ${ap}` : `${h12}:${mm} ${ap}`;
}
const takenList = (d) => String(d || '').replace(/^booked\s*/i, '').split(',').map(x => timeLabel(x.trim().toLowerCase())).filter(Boolean).join(', ');
const slotLine = (f) => `${(f.slots.date || '').toUpperCase()}${f.slots.time && f.slots.time !== 'all-day' ? ', ' + timeLabel(f.slots.time) : (f.slots.time === 'all-day' ? ', ALL DAY' : '')}`.trim();

/** Tabella "formato del frame per stato" di plan/ramo-hud.md. */
function themeFor() {
    // Regola (07/09): lo schermo e' DOMANDA e RISPOSTA, al massimo tre righe, tutte pronunciabili al cliente cosi' come sono.
    // Niente istruzioni per l'operatore, niente elenchi non richiesti: i giorni occupati compaiono solo se la domanda e' sul mese.
    const f = hud.fsm;
    switch (hud.screen) {
        case 'COLLECTING': {
            const miss = (f.missing || [])[0] || '';
            const month = (f.slots.month || '').toUpperCase(), day = f.slots.day || '';
            const rejKeys = Object.keys(f.rejected || {});
            const tent = f.tentative || {};
            const mq = tent.month ? '?' : '', dq = tent.day ? '?' : '', tq = tent.time ? '?' : '';
            const when = (month || day) ? `${month ? month + mq : ''}${day ? ' ' + day + dq : ''}`.trim() : '';
            const verb = f.intent === 'check' ? 'FREE' : 'BOOK';
            const line1 = when ? `${verb}: ${when}${f.slots.time && miss !== 'time' ? ', ' + timeLabel(f.slots.time) + tq : ''}` : `${verb}: ?`;
            const askFor = { month: 'WHICH MONTH?', day: 'WHICH DAY?', time: 'WHAT TIME?' }[miss] || '';
            const tentKeys = Object.keys(tent).filter(k => tent[k]);
            // tentativo "proposal" (BETAGAMMA 08/09) = proposta dell'operatore verificata libera: la domanda e' la sua ("does that work?")
            const proposal = tentKeys.some(k => tent[k] === 'proposal');
            let line2 = tentKeys.length ? (proposal ? 'DOES THAT WORK?' : 'IS THAT RIGHT?') : askFor, line3 = '';
            if (f.intent === 'check' && f.month_info && !f.slots.day) {   // domanda sul mese: la risposta e' del mese
                const bd = f.month_info.booked_days || [];
                line2 = bd.length ? `FREE, EXCEPT ${bd.join(', ')}` : 'ALL DAYS FREE'; line3 = askFor;
            }
            if (rejKeys.length) {
                const v = String(f.rejected[rejKeys[0]]).toUpperCase();
                line2 = / TAKEN$| FULL$/.test(v) ? v : `${v}: NOT VALID`;
            }
            return { bg: rejKeys.length ? '#c62828' : '#1565c0', fg: '#ffffff', title: '', line1, line2, line3 };
        }
        case 'CHECKING':
            return { bg: '#f9a825', fg: '#1a1a1a', title: '', line1: slotLine(f), line2: 'ONE MOMENT', line3: '' };
        case 'CONFIRM':
        case 'DONE': {
            const s = f.status, d = (f.detail || '');
            if (s === 'error') return { bg: '#b71c1c', fg: '#ffffff', title: '', line1: slotLine(f), line2: 'SYSTEM ERROR, PLEASE RETRY', line3: '' };
            // (08/09, GOODTEST-2) risultato = riga 1 lo slot, riga 2 un FATTO (FREE / TAKEN / BOOKED, mai YES/NO che si confonde
            // con il si' del cliente), riga 3 la domanda che l'operatore fa al cliente per il passo successivo.
            const slot = slotLine(f);
            if (f.intent === 'book') {
                if (s === 'pending') return { bg: '#2e7d32', fg: '#ffffff', title: '', line1: slot, line2: 'FREE', line3: hud.screen === 'CONFIRM' ? 'SHALL I BOOK IT?' : '' };
                if (s === 'confirmed') return { bg: '#2e7d32', fg: '#ffffff', title: '', line1: slot, line2: 'BOOKED', line3: 'ANYTHING ELSE?' };
                return { bg: '#c62828', fg: '#ffffff', title: '', line1: slot, line2: 'TAKEN', line3: '' };
            }
            const allDay = !f.slots.time || f.slots.time === 'all-day';
            const fact = s === 'available' ? 'FREE' : (s === 'partial' ? `FREE, EXCEPT ${takenList(d)}` : 'TAKEN');
            const bg = s === 'available' ? '#2e7d32' : (s === 'partial' ? '#ef6c00' : '#c62828');
            const next = hud.screen !== 'CONFIRM' || s === 'booked' ? '' : (allDay ? 'WHAT TIME?' : 'SHALL I BOOK IT?');
            return { bg, fg: '#ffffff', title: '', line1: slot, line2: fact, line3: next };
        }
        default:
            return { bg: '#263238', fg: '#eceff1', title: 'BOOKING DESK', line1: f.note || '', line2: '', line3: '' };
    }
}

/** Due tonalita' dello stesso colore, alternate a ogni cambio di stato (seq): cosi' anche quando il testo resta uguale
 *  (stesso MISSING dopo un valore respinto, conferma -> conferma con valori simili) i pixel cambiano e l'omni rilegge. */
function shade(hex, k) {
    const n = parseInt(hex.slice(1), 16);
    const c = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map(v => Math.max(0, Math.min(255, Math.round(v * k))));
    return '#' + c.map(v => v.toString(16).padStart(2, '0')).join('');
}
function themeForSeq() {
    const theme = themeFor();
    if ((hud.fsm.seq || 0) % 2 === 1) theme.bg = shade(theme.bg, 0.78);
    return theme;
}

/** L'ATTO (meta' sopra dello schermo a due meta'): verbo + oggetto, dalla tabella stato -> atto. Mai "wait". */
function actFor() {
    const f = hud.fsm, s = f.status;
    switch (hud.screen) {
        case 'COLLECTING': {
            const tentKeys = Object.keys(f.tentative || {}).filter(k => f.tentative[k]);
            if (tentKeys.length) return `CONFIRM: ${tentKeys[0].toUpperCase()}`;   // valore dell'operatore da confermare col cliente
            const miss = (f.missing || [])[0] || '';
            return miss ? `ASK: ${miss.toUpperCase()}` : '';   // il perche' (15:00 TAKEN) sta nello stato, non nell'atto
        }
        case 'CHECKING': return 'SAY: CHECKING';
        case 'CONFIRM': return f.intent === 'book' ? 'ASK: CONFIRM BOOKING' : 'SAY: AVAILABLE';
        case 'DONE':
            if (s === 'error') return 'SAY: ERROR';
            if (f.intent === 'book') return s === 'confirmed' ? 'SAY: BOOKED' : 'SAY: SLOT TAKEN';
            return s === 'available' ? 'SAY: AVAILABLE' : (s === 'partial' ? 'SAY: PARTLY FREE' : 'SAY: ALREADY BOOKED');
        default: return f.note ? 'SAY: CANCELLED' : '';
    }
}

// ramo hud-semaforo: verde = l'omni guida (solo stato); giallo = atto dettato; rosso = correzione fissa. Il banner
// lampeggia (3 frame alternati) a ogni cambio di livello per richiamare l'attenzione.
const LIGHT = { green: '#2e7d32', yellow: '#f9a825', red: '#c62828' };
let blinkLeft = 0, blinkPhase = 0, lastLevelSeen = 'green';
function drawHud() {
    const W = canvas.width, H = canvas.height, theme = themeForSeq();
    const level = hud.fsm.level || 'green', hint = hud.fsm.hint || '';
    ctx.fillStyle = theme.bg; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = theme.fg; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    // banner del semaforo in alto (lampeggia: colore pieno / bianco a fasi alterne)
    const on = ($('blinkAlways') && $('blinkAlways').checked) || blinkLeft > 0 ? (blinkPhase % 2 === 0) : true;
    ctx.fillStyle = on ? LIGHT[level] : '#ffffff'; ctx.fillRect(0, 0, W, H * 0.16);
    ctx.fillStyle = on ? '#ffffff' : LIGHT[level];
    const bannerText = level === 'green' ? 'OK' : (level === 'yellow' ? `⚠ ${hint || 'CHECK THE SCREEN'}` : `■ ${hint || 'STOP'}`);
    if (bannerText.length <= 22) { ctx.font = 'bold 30px system-ui, sans-serif'; ctx.fillText(bannerText, W / 2, H * 0.08); }
    else {   // frase del supervisore: due righe, font ridotto
        ctx.font = 'bold 19px system-ui, sans-serif';
        const words = bannerText.split(' '), lines = ['']; for (const w of words) { const t = (lines[lines.length - 1] + ' ' + w).trim(); if (ctx.measureText(t).width > W * 0.94 && lines[lines.length - 1]) lines.push(w); else lines[lines.length - 1] = t; }
        const shown = lines.slice(0, 2); if (lines.length > 2) shown[1] += '…';
        shown.forEach((ln, i) => ctx.fillText(ln, W / 2, H * (shown.length === 1 ? 0.08 : 0.05 + i * 0.06)));
    }
    ctx.fillStyle = theme.fg;
    const act = '';   // 07/09: NESSUN atto sullo schermo. Regola: ogni riga deve essere pronunciabile al cliente cosi' com'e'; le istruzioni per l'operatore venivano lette alla lettera ('I'm going to ask the day')
    hud.lastText = [bannerText, act, theme.title, theme.line1, theme.line2, theme.line3 || ''].filter(Boolean).join(' | ');
    if (act) {
        // schermo a due meta': sopra l'atto, sotto lo stato (linea di separazione)
        ctx.font = 'bold 40px system-ui, sans-serif'; ctx.fillText(act, W / 2, H * 0.29);
        ctx.globalAlpha = 0.75; ctx.fillRect(W * 0.08, H * 0.40, W * 0.84, 3); ctx.globalAlpha = 1;
        ctx.font = 'bold 22px system-ui, sans-serif'; ctx.fillText(theme.title, W / 2, H * 0.50);
        ctx.font = (theme.line1.length > 18 ? 'bold 26px' : 'bold 34px') + ' system-ui, sans-serif'; ctx.fillText(theme.line1, W / 2, H * 0.63);
        ctx.font = (theme.line2.length > 12 ? 'bold 26px' : 'bold 34px') + ' system-ui, sans-serif'; ctx.fillText(theme.line2, W / 2, H * 0.76);
        if (theme.line3) { ctx.font = (theme.line3.length > 28 ? 'bold 14px' : 'bold 18px') + ' system-ui, sans-serif'; ctx.fillText(theme.line3, W / 2, H * 0.86); }
    } else {
        const fit = (text, max, y) => { let sz = max; ctx.font = `bold ${sz}px system-ui, sans-serif`; while (ctx.measureText(text).width > W * 0.92 && sz > 14) { sz -= 2; ctx.font = `bold ${sz}px system-ui, sans-serif`; } ctx.fillText(text, W / 2, y); };
        if (theme.title) fit(theme.title, 34, H * 0.30);
        if (theme.line1) fit(theme.line1, 40, H * (theme.title ? 0.50 : 0.42));
        if (theme.line2) fit(theme.line2, 52, H * (theme.title ? 0.68 : 0.62));
        if (theme.line3) fit(theme.line3, 28, H * 0.80);
    }
    ctx.font = '18px system-ui, sans-serif'; ctx.globalAlpha = 0.7; ctx.fillText('operator screen', W / 2, H * 0.92); ctx.globalAlpha = 1;
    $('hudState').textContent = hud.screen + (hud.fsm.status ? ' ' + hud.fsm.status.toUpperCase() : '') + ((hud.fsm.missing || []).length ? ' (missing ' + hud.fsm.missing.join(',') + ')' : '');
}

/** Gate sul cambio: produce un frame SOLO se lo stato e' cambiato dall'ultimo frame inviato. */
function hudSync(force = false) {
    drawHud();
    const h = hud.fingerprint();
    if (!force && h === hud.lastHash) return;
    hud.lastHash = h;
    const content = h.replace(/\|b\d*/, '');   // impronta di CONTENUTO (senza fase del lampeggio)
    if (content !== hud.lastContent) { hud.lastContent = content; hud.pendingIsEvent = true; if ($('stickyScreen').checked) pendingContext = true; }
    hud.pendingFrame = canvas.toDataURL('image/jpeg', 0.85).split(',')[1];
    hudLog('hud', `frame pronto (${$('hudState').textContent}) → allegato al prossimo chunk audio · schermo: ${hud.lastText || ''}`);
}

/** Etichetta per db.html (pill): IDLE / COLLECTING / CHECKING / OK / PARTIAL / NO / ERR. */
function screenLabel() {
    const f = hud.fsm;
    if (hud.screen !== 'CONFIRM' && hud.screen !== 'DONE') return hud.screen;
    if (f.status === 'error') return 'ERR';
    if (f.status === 'available' || f.status === 'confirmed' || f.status === 'pending') return 'OK';
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
    if ((fsm.level || 'green') !== lastLevelSeen) { lastLevelSeen = fsm.level || 'green'; blinkLeft = 4; blinkPhase = 0; }   // lampeggio: 4 frame alternati
    const prevFsm = hud.fsm; hud.fsm = fsm;
    dbgFsm(prevFsm, fsm);   // grafo di debug: ultimo passaggio
    if ((fsm.state === 'CONFIRM' || fsm.state === 'DONE') && delay > 0 && changed && hud.screen !== 'CONFIRM' && hud.screen !== 'DONE') {
        hud.screen = 'CHECKING'; syncScreen();
        queryTimer = setTimeout(() => { hud.screen = fsm.state; syncScreen(); hudLog('sys', `esito mostrato dopo ${delay}s: ${fsm.status}${fsm.detail ? ' (' + fsm.detail + ')' : ''}`); }, delay * 1000);
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
    dbg.event = { t: now(), calls: toolCalls, text: userText || '', changed: !!d.changed, source };
    if (d.changed && lastHelp) { hudLog('sys', 'aiuto di σ superato: la macchina e\' cambiata con la battuta del cliente'); lastHelp = ''; }   // (08/09) un aiuto vale per lo stato in cui e' nato
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
    const args = {}; if (!['yes', 'no', 'cancel'].includes(intent)) { if (date) args.date = date; if (time) args.time = time; }
    hudLog('sys', `richiesta manuale: ${intent}(${JSON.stringify(args)})`);
    fsmEvent([{ name: intent, arguments: args }], '', 'manuale').catch(e => hudLog('warn', 'FSM errore: ' + e.message));
}

// ------------------------------------------------------------------ microfono + VAD
/** VAD a energia, risoluzione 100 ms: parli -> accumula; taci per `silenceMs` -> fine turno (callback con l'audio della battuta). */
class TurnDetector {
    constructor(onTurnEnd, onPause, onResume) {
        this.onTurnEnd = onTurnEnd; this.onPause = onPause || (() => {}); this.onResume = onResume || (() => {});
        this.speaking = false; this.speechMs = 0; this.silenceMs = 0; this.frames = []; this.preroll = []; this.ctx = []; this.pausedFired = false;
    }
    // audio della battuta PRECEDUTO da fino a 3 s di contesto (Whisper sbaglia di piu' sulle clip corte: "April" -> "incredible");
    // il servizio ASR scarta dalla trascrizione cio' che finisce dentro il contesto
    audioSoFar() {
        const all = this.ctx.concat(this.frames);
        const n = all.reduce((a, f) => a + f.length, 0); const out = new Float32Array(n); let o = 0;
        for (const f of all) { out.set(f, o); o += f.length; }
        return out;
    }
    contextSec() { return this.ctx.length * 0.1; }
    params() {
        return { thr: parseFloat($('vadThr').value) || 0.02, silence: parseInt($('vadSilence').value, 10) || 600, minSpeech: parseInt($('vadMin').value, 10) || 300 };
    }
    feed(frame) {   // frame = Float32Array da 100 ms
        const { thr, silence, minSpeech } = this.params();
        let e = 0; for (let i = 0; i < frame.length; i++) e += frame[i] * frame[i]; const rms = Math.sqrt(e / frame.length);
        $('vadMeter').textContent = rms.toFixed(3); $('vadState').textContent = this.speaking ? 'PARLI' : 'silenzio';
        if (!this.speaking) {
            this.preroll.push(frame); if (this.preroll.length > 3) this.preroll.shift();    // 300 ms prima dell'attacco (i 3 s di contesto: misurati inutili, il mic in silenzio manda zeri)
            if (rms > thr) { this.speaking = true; this.speechMs = 100; this.silenceMs = 0; this.ctx = this.preroll.slice(); this.frames = [frame]; }
            return;
        }
        this.frames.push(frame);
        if (rms > thr) {
            this.speechMs += 100; this.silenceMs = 0;
            if (this.pausedFired) { this.pausedFired = false; this.onResume(); }   // ha ripreso: la decisione anticipata e' stale
        } else { this.silenceMs += 100; }
        // pausa di 300 ms: si parte SUBITO con ASR + estrattore sull'audio detto finora (decisione anticipata);
        // il risultato si applica solo se il turno finisce senza altra voce (nessun evento da frasi a meta')
        if (this.silenceMs === 300 && this.speechMs >= minSpeech && !this.pausedFired) { this.pausedFired = true; this.onPause(this.audioSoFar(), this.speechMs, this.contextSec()); }
        if (this.silenceMs >= silence) {
            const spoke = this.speechMs >= minSpeech; const speechMs = this.speechMs; const out = this.audioSoFar(); const ctxSec = this.contextSec();
            this.speaking = false; this.frames = []; this.preroll = []; this.ctx = []; this.speechMs = 0; this.silenceMs = 0; this.pausedFired = false;
            if (spoke) this.onTurnEnd(out, speechMs, ctxSec);
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
    return `STATO [${tag}] KV ${m.kvCacheLength ?? '?'} · finestra ${win} · FSM ${fsm} · semaforo ${f.level || 'green'}${f.hint ? ' ' + f.hint : ''} · lp ${$('lengthPenalty').value} trp ${$('textRepPenalty').value}`;
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
    $('btnStart').disabled = on; $('btnStop').disabled = !on; $('btnForceListen').disabled = !on; $('btnForceSpeak').disabled = !on; $('btnCue').disabled = !on;
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
    hud.lastContent = null; hud.pendingIsEvent = false; pendingContext = false; instructionActive = ''; clearTimeout(instructionTimer);
    omniTurnOpen = false; lastUserTurnAt = -1; lastForceAt = -100; forceCount = {}; forceLatched = false; holdActive = false; clearTimeout(silenceTimer);
    lastOmniEndAt = -1; clearTimeout(noReplyTimer); sigmaBusy = false; lastHelp = ''; forcesSinceUser = 0; clearTimeout(midTurnTimer); cutChunksLeft = 0; cutVerdict = null; cutsSinceUser = 0;
    await fsmReset();                                // ogni sessione parte da IDLE (le prenotazioni in db.html restano)
    hud.pendingFrame = null; hud.lastHash = null;   // il frame iniziale lo decide la spunta
    t0ms.v = performance.now();
    userLines.length = 0; dialog.length = 0; currentAiText = '';

    session = new RealtimeSession('hud', {
        getMaxKvTokens: () => ($('slidingWindow').value === 'basic' ? 8192 : 16384),
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
        omniSpokeAt = now(); omniTurnOpen = true; clearTimeout(silenceTimer); armMidTurnCheck(MID_TURN_FIRST_S);
        const el = conv('ai', 'AI: ' + (text || ''));
        el.dataset.prefix = 'AI: ';
        onModelText(text || '');
        return el;
    };
    session.onSpeakUpdate = (el, text) => { if (el) { el.textContent = ''; el.innerHTML = `<span class="t">${now().toFixed(1)}s</span>`; el.appendChild(document.createTextNode('AI: ' + text)); } onModelText(text || ''); };
    // fine del turno dell'omni: la libreria chiama onSpeakEnd (il modelState 'end_of_turn' delle metriche non arriva mai)
    session.onSpeakEnd = () => {
        omniTurnOpen = false; lastOmniEndAt = now(); clearInstruction('turno finito'); clearTimeout(midTurnTimer);
        conv('sys', stateLine('fine turno AI'));
        if (currentAiText) {
            const said = currentAiText; currentAiText = '';
            runLogPush($('conv'), 'ai', 'AI (turno completo): ' + said);   // solo registro: la riga viva in pagina si aggiorna da sola
            dialog.push({ role: 'assistant', text: said }); if (dialog.length > 40) dialog.shift();
            const forced = forceSpeakSentAt >= 0 && omniSpokeAt >= forceSpeakSentAt && omniSpokeAt - forceSpeakSentAt < 3;
            const informed = lastUserTurnAt >= 0 && omniSpokeAt >= lastUserTurnAt && omniSpokeAt - lastUserTurnAt < 6;   // turno iniziato DOPO la tua battuta: i readback valgono
            if (cutVerdict) { const v = cutVerdict; cutVerdict = null; cutChunksLeft = 0; onOperatorTurnEnd(said, false, 'cut', v); }
            else onOperatorTurnEnd(said, forced && !informed);
        }
    };
    session.onListenResult = (r) => { if (r && r.text) conv('sys', 'utente: ' + r.text); };
    session.onMetrics = (d) => {
        if (!d) return;
        if (d.sessionState) $('stateText').textContent = d.sessionState;
        if (d.kvCacheLength !== undefined) lastMetrics = d;
        if (d.modelState) lastModelState = d.modelState;
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
                                       sliding_window_mode: $('slidingWindow').value, sliding_window_high_tokens: 4000, sliding_window_low_tokens: 3500,
                                       context_max_units: 45, context_previous_max_tokens: 500 },
                             use_tts: true, max_slice_nums: 1 };
    conv('sys', `CONFIG · prompt: "${$('systemPrompt').value}" · autoForce ${$('autoForce').checked ? 'on' : 'off'} · hold ${$('holdOn').checked ? 'on' : 'off'} · sticky ${$('stickyScreen').checked ? 'on' : 'off'} · inject ${$('injectMode').value} · heard ${$('heardOn').checked ? 'on' : 'off'} · blink ${($('blinkAlways') && $('blinkAlways').checked) ? 'on' : 'off'}` + ` · asr ${$('asrProfile') ? $('asrProfile').value : '?'} · finestra ${$('slidingWindow').value} · trp ${$('textRepPenalty').value}`);   // nel registro della run
    lastWindowEvents = 0; lastMetrics = {}; lastModelState = ''; $('kvInfo').textContent = 'KV: — · finestra: ' + $('slidingWindow').value;
    const ref = await loadRefAudio();
    if (ref) preparePayload.ref_audio_base64 = ref;

    const sess = session;   // il microfono spedisce SOLO alla sessione per cui e' stato creato
    try {
        await sess.start($('systemPrompt').value, preparePayload, async () => {
            if ($('sendInitial').checked) hudSync(true);
            const turns = new TurnDetector((utterance, speechMs, ctxSec) => onUserTurnEnd(utterance, speechMs, ctxSec),
                                           (audio, speechMs, ctxSec) => onUserPause(audio, speechMs, ctxSec), () => { if (speculative) speculative.stale = true; });
            mic = new MicCapture((audioF32) => {
                if (cueOnce && cueSamples) {   // stimolo acustico: il clip prende il posto del microfono per questo chunk
                    cueOnce = false; const mixed = new Float32Array(audioF32.length);
                    mixed.set(cueSamples.subarray(0, Math.min(cueSamples.length, mixed.length)));
                    audioF32 = mixed; hudLog('warn', `STIMOLO AUDIO inviato con il chunk #${sess.chunksSent + 1}`);
                }
                const msg = { type: 'audio_chunk', audio_base64: arrayBufferToBase64(audioF32.buffer) };
                if (pendingContext) {
                    pendingContext = false; msg.context_text = composeContext();
                    if ($('slidingWindow').value !== 'context') hudLog('warn', 'regione sticky ignorata dal modello: serve la finestra in modo context');
                    else hudLog('hud', `CONTEXT → regione di sistema (chunk #${sess.chunksSent + 1}): "${msg.context_text.replace(/\n/g, ' ⏎ ')}"`);
                }
                // hold (opzione): dalla pausa alla decisione l'omni ascolta (force_listen), al massimo HOLD_MAX_CHUNKS chunk
                if (holdActive) {
                    if (holdChunks < HOLD_MAX_CHUNKS) { msg.force_listen = true; holdChunks++; hudLog('sys', `HOLD: force_listen sul chunk #${sess.chunksSent + 1}`); }
                    else { holdActive = false; forceLatched = true; latchReason = 'hold scaduto'; hudLog('warn', 'HOLD scaduto: force armato'); }
                }
                // lampeggio: costante (un frame per chunk, banner alternato) oppure solo 4 frame al cambio di livello
                if (!hud.pendingFrame && ($('blinkAlways').checked || blinkLeft > 0)) { blinkPhase++; if (blinkLeft > 0) blinkLeft--; hudSync(true); }
                let isEvent = false;
                if (hud.pendingFrame) {
                    msg.frame_base64_list = [hud.pendingFrame];
                    hud.pendingFrame = null; hud.framesSent++; hud.lastFrameAt = now(); awaitingReaction = true;
                    isEvent = !!hud.pendingIsEvent; hud.pendingIsEvent = false;
                    $('framesSent').textContent = hud.framesSent;
                    $('frameInfo').textContent = `ultimo frame inviato a ${hud.lastFrameAt.toFixed(1)}s (${$('hudState').textContent})`;
                    hudLog('hud', `FRAME INVIATO (${$('hudState').textContent}) con il chunk #${sess.chunksSent + 1}${isEvent ? ' · EVENTO' : ''}`);
                }
                // TAGLIO (σ in corsa): force_listen per un chunk, audio fermato subito
                if (cutChunksLeft > 0) {
                    cutChunksLeft--; msg.force_listen = true;
                    try { sess.audioPlayer.stopAll(); } catch (_) {}
                    hudLog('warn', `TAGLIO: force_listen sul chunk #${sess.chunksSent + 1} (il modello chiude il turno con <|turn_eos|>)`);
                }
                // politica τ: manuale > evento > latch/guardiano
                let why = '';
                if (forceSpeakOnce && !msg.force_listen) { forceSpeakOnce = false; why = 'manuale'; }
                else if ($('autoForce').checked && !msg.force_listen) {
                    if (isEvent && (sess.chunksSent + 1) >= 4) {
                        const resultFrame = hud.screen === 'CONFIRM' || hud.screen === 'DONE' || (hud.fsm.level && hud.fsm.level !== 'green');
                        if (canForceNow(turns, sess)) why = 'evento';
                        else if (resultFrame) { forceLatched = true; latchReason = 'evento'; hudLog('sys', `frame RISULTATO con turno ${omniTurnOpen ? 'aperto' : 'chiuso'}${turns.speaking ? ', voce' : ''}: force ARMATO`); }
                        else hudLog('sys', 'frame evento (raccolta) con turno aperto: la risposta in corso basta, nessun latch');
                    } else if (forceLatched && canForceNow(turns, sess)) { why = 'latch ' + latchReason; forceLatched = false; }
                }
                if (why) {
                    msg.force_speak = true; forceSpeakSentAt = now(); lastForceAt = forceSpeakSentAt; forceCount[hud.fsm.seq || 0] = (forceCount[hud.fsm.seq || 0] || 0) + 1;
                    const mode = why === 'manuale' ? $('injectMode').value : 'none', inj = mode === 'none' ? '' : injectTextNow();
                    if (inj && mode === 'unit') msg.inject_text = inj;
                    if (inj && mode === 'system') { instructionActive = inj; pendingContext = true; clearTimeout(instructionTimer); instructionTimer = setTimeout(() => clearInstruction('timeout 8 s'), 8000); }
                    const chunkNo = sess.chunksSent + 1, sentAt = forceSpeakSentAt;
                    hudLog('warn', `FORCE_SPEAK (${why}) con il chunk #${chunkNo} (schermo: ${hud.lastText || ''})${inj ? ' · ' + (mode === 'system' ? 'ISTRUZIONE in regione di sistema' : 'INIETTATO nello slot di uscita') + ': "' + inj + '"' : ''}`);
                    dbg.force = { t: sentAt, why, chunk: chunkNo, screen: hud.lastText || '' }; renderGraph();
                    if (pendingContext) { pendingContext = false; msg.context_text = composeContext(); hudLog('hud', `CONTEXT → regione di sistema (chunk #${chunkNo}): "${msg.context_text.replace(/\n/g, ' ⏎ ')}"`); }
                    setTimeout(() => hudLog(omniSpokeAt > sentAt ? 'hud' : 'warn', `FORCE_SPEAK #${chunkNo} → ${omniSpokeAt > sentAt ? 'turno aperto a +' + (omniSpokeAt - sentAt).toFixed(1) + ' s' : 'NESSUN TESTO entro 3 s (turno vuoto o ignorato)'}`), 3000);
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
let currentAiText = '';
function onModelText(text) {
    if (!text) return;
    currentAiText = text;
    if (awaitingReaction && hud.lastFrameAt !== null) {
        awaitingReaction = false;
        hudLog('hud', `REAZIONE +${(now() - hud.lastFrameAt).toFixed(1)}s dopo il frame (${$('hudState').textContent}): "${text.slice(0, 60)}"`);
    }
}

// ---- estrattore (modello SEPARATO): riceve SOLO le battute dell'utente + lo stato della FSM
const userLines = [];           // ultime battute dell'utente (ASR)
const dialog = [];              // ultime righe del dialogo (operatore + utente): le usa solo il backend cloud (PROMPT_API)
let toolBusy = false;
const pendingTurns = [];        // battute arrivate mentre l'estrattore era occupato: si accodano, non si scartano

/** Chiama ASR + estrattore su una battuta (non applica nulla). */
async function decideUtterance(utterance, ctxSec = 0) {
    const t0 = performance.now();
    const transcript = dialog.slice(-8);
    const r = await fetch('/api/tool_agent/decide', { method: 'POST', headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ transcript, user_audio_b64: arrayBufferToBase64(utterance.buffer), language: 'en', fsm: hud.fsm, context_s: ctxSec }) });
    const d = await r.json();
    return { ok: r.ok, status: r.status, d, dt: ((performance.now() - t0) / 1000).toFixed(2), fsmSeq: hud.fsm.seq || 0 };
}

// decisione anticipata: parte alla prima pausa di 300 ms, si usa a fine turno se nel frattempo non hai ripreso a parlare
let speculative = null;
function onUserPause(audio, speechMs, ctxSec) {
    if ($('trigMode').value !== 'tool' || toolBusy) return;
    if ($('holdOn').checked && !omniTurnOpen) { holdActive = true; holdChunks = 0; }
    const t0 = performance.now();
    speculative = { speechMs, stale: false, t0, promise: decideUtterance(audio, ctxSec).catch(e => ({ ok: false, status: 0, d: { error: e.message }, dt: '?' })) };
}

/** Fine del tuo turno: ASR della sola battuta (GPU) + estrazione + evento alla FSM. */
async function onUserTurnEnd(utterance, speechMs, ctxSec = 0) {
    const secs = (utterance.length / SR_IN - ctxSec).toFixed(1);
    hudLog('sys', `TURNO UTENTE finito (${secs} s di voce + ${ctxSec.toFixed(1)} s di contesto)`);
    if ($('trigMode').value !== 'tool') return;
    if (toolBusy) { pendingTurns.push(utterance); if (pendingTurns.length > 2) pendingTurns.shift(); hudLog('sys', `estrattore occupato: battuta in coda (${pendingTurns.length})`); return; }
    toolBusy = true;
    try {
        let res;
        const spec = speculative; speculative = null;
        if (spec && !spec.stale && spec.speechMs === speechMs) {
            // stessa voce della pausa: il risultato anticipato vale per tutto il turno
            res = await spec.promise;
            hudLog('sys', `decisione anticipata alla pausa: usata (partita ${((performance.now() - spec.t0) / 1000).toFixed(1)} s fa, calcolo ${res.dt} s)`);
        } else {
            if (spec) hudLog('sys', 'decisione anticipata scartata (hai ripreso a parlare)');
            res = await decideUtterance(utterance, ctxSec);
        }
        const { ok, status, d, dt } = res;
        if (!ok) { hudLog('warn', `estrattore: ${d.error || status}`); return; }
        if (d.user_text) { lastUserTurnAt = now(); forcesSinceUser = 0; cutsSinceUser = 0; userTurns++; lastUserWords = d.user_text.trim().split(/\s+/).length; conv('sys', 'TU (ASR): ' + d.user_text); userLines.push(d.user_text); if (userLines.length > 4) userLines.shift(); dialog.push({ role: 'user', text: d.user_text }); if (dialog.length > 40) dialog.shift(); }
        const calls = d.tool_calls || [];
        const tim = `ASR ${d.asr_s ?? '?'} s${d.asr_model ? ' (' + d.asr_model + ')' : ''} + LLM ${d.llm_s ?? '?'} s = ${dt} s${d.backend ? ' · ' + d.backend : ''}`;
        if (!calls.length) { hudLog('sys', `estrattore (${tim}): nessuna azione — "${(d.raw || '').slice(0, 70)}"`); return; }
        for (const c of calls) hudLog('hud', `ESTRATTORE (${tim}): ${c.name}(${JSON.stringify(c.arguments)})`);
        await fsmEvent(calls, d.user_text, 'estrattore (turno utente)');
        conv('sys', stateLine(`dopo la tua battuta: ${calls.map(c => c.name + JSON.stringify(c.arguments)).join(' ')}`));
    } catch (e) { hudLog('warn', 'estrattore errore: ' + e.message); }
    finally {
        toolBusy = false;
        if (holdActive) { holdActive = false; forceLatched = true; latchReason = 'hold rilasciato'; }
        if (lastUserTurnAt >= 0 && now() - lastUserTurnAt < 5) armNoReplyCheck();   // decide σ se il silenzio e' un problema (un filler no, una domanda si')
        if ($('autoForce').checked && lastUserTurnAt >= 0 && now() - lastUserTurnAt < 5 && lastUserWords >= 3) armSilenceWatchdog();
        if (pendingTurns.length) onUserTurnEnd(pendingTurns.shift());
    }
}

async function refreshAsrProfile() {
    try {
        const d = await (await fetch('/api/hud/asr_profile', { cache: 'no-store' })).json();
        if (d.profile === 'turbo' || d.profile === 'small') $('asrProfile').value = d.profile;
        $('asrProfileState').textContent = d.switching ? 'cambio in corso…' : `attivo: ASR ${d.asr} · estrattore ${d.tool_agent}`;
        return d;
    } catch (e) { $('asrProfileState').textContent = 'stato non leggibile'; return null; }
}
$('btnAsrProfile').onclick = async () => {
    const profile = $('asrProfile').value;
    $('asrProfileState').textContent = 'riavvio ASR ed estrattore…';
    const r = await fetch('/api/hud/asr_profile', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ profile }) });
    if (!r.ok) { $('asrProfileState').textContent = 'errore: ' + ((await r.json()).error || r.status); return; }
    const t0 = Date.now();
    const poll = setInterval(async () => {
        const d = await refreshAsrProfile();
        if (d && !d.switching && d.asr !== 'down' && d.tool_agent !== 'down') { clearInterval(poll); checkToolAgent(); }
        if (Date.now() - t0 > 180000) clearInterval(poll);
    }, 3000);
};
refreshAsrProfile();

/** Fine turno dell'omni (ramo hud-semaforo): heard (se attivo e in raccolta) + giudizio deterministico del turno. */
// σ stuck detector (07/09): a fine turno dell'omni e, se dopo una tua battuta non risponde entro NO_REPLY_S, con reason 'no_reply'.
// Vede conversazione, schermo, stato e tempi; decide ok/stuck. Stuck -> giallo con l'aiuto sullo schermo + force_speak nudo.
const NO_REPLY_S = 3;
let lastOmniEndAt = -1, noReplyTimer = null, sigmaBusy = false, lastHelp = '', forcesSinceUser = 0;
// σ in corsa (08/09, proposta 1): a MID_TURN_FIRST_S di turno aperto e poi ogni MID_TURN_EVERY_S, σ giudica il testo parziale;
// stuck -> TAGLIO: force_listen per un chunk (il modello chiude il turno con <|turn_eos|>), audio fermato; a turno chiuso il
// verdetto del taglio va al semaforo (reason 'cut': niente readback ne' claim nel record) -> aiuto + force_speak come sempre.
const MID_TURN_FIRST_S = 10, MID_TURN_EVERY_S = 8, MAX_CUTS_PER_USER_TURN = 3;
let midTurnTimer = null, cutChunksLeft = 0, cutVerdict = null, cutsSinceUser = 0;
function armMidTurnCheck(delayS) {
    clearTimeout(midTurnTimer);
    midTurnTimer = setTimeout(midTurnCheck, delayS * 1000);
}
async function midTurnCheck() {
    if (!session || !omniTurnOpen || !$('midTurnOn').checked || !$('heardOn').checked || cutVerdict) return;
    if (sigmaBusy) { armMidTurnCheck(2); return; }
    const turnS = +(now() - omniSpokeAt).toFixed(1), partial = currentAiText || '';
    const seqSeen = hud.fsm.seq || 0;
    try {
        sigmaBusy = true;
        const t0 = performance.now();
        const timing = { since_user_s: lastUserTurnAt >= 0 ? +(now() - lastUserTurnAt).toFixed(1) : null, since_omni_s: null, omni_speaking: true, turn_s: turnS };
        const r = await fetch('/api/tool_agent/sigma', { method: 'POST', headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ operator_text: partial, fsm: hud.fsm, transcript: dialog.slice(-40), screen: hud.lastText || '', reason: 'mid_turn', timing, previous_help: lastHelp }) });
        const d = await r.json(); sigmaBusy = false;
        const dt = ((performance.now() - t0) / 1000).toFixed(2);
        if (!r.ok) { hudLog('warn', `σ in corsa: ${d.error || r.status}`); armMidTurnCheck(MID_TURN_EVERY_S); return; }
        const a = ((d.tool_calls || [])[0] || {}).arguments || null;
        dbg.sigma = { t: now(), reason: 'mid_turn', a: a ? Object.assign({}, a) : null, text: partial, turnS }; renderGraph();
        if (!omniTurnOpen) { hudLog('sys', `σ in corsa (${dt} s, turno di ${turnS} s): il turno si e' chiuso da solo nel frattempo`); return; }
        if (a && a.status === 'stuck') {
            if (cutsSinceUser >= MAX_CUTS_PER_USER_TURN) { hudLog('warn', `σ in corsa (${dt} s, turno di ${turnS} s): STUCK ${a.kind || ''} ma tetto di ${MAX_CUTS_PER_USER_TURN} tagli per battuta raggiunto: tocca al cliente`); return; }
            cutsSinceUser++; cutChunksLeft = 1;
            cutVerdict = { calls: [{ name: 'sigma', arguments: { status: 'stuck', kind: a.kind || null, help: a.help || null } }], seq: seqSeen, turnS, text: partial };
            hudLog('warn', `σ in corsa (${dt} s, turno di ${turnS} s): STUCK ${a.kind || ''}${a.help ? ' → "' + a.help + '"' : ''} → TAGLIO: force_listen col prossimo chunk — "${partial.slice(-80)}"`);
        } else {
            hudLog('sys', `σ in corsa (${dt} s, turno di ${turnS} s): ok — "${partial.slice(-60)}"`);
            armMidTurnCheck(MID_TURN_EVERY_S);
        }
    } catch (e) { sigmaBusy = false; hudLog('warn', 'σ in corsa errore: ' + e.message); armMidTurnCheck(MID_TURN_EVERY_S); }
}
function armNoReplyCheck() {
    clearTimeout(noReplyTimer);
    noReplyTimer = setTimeout(() => {
        if (!session || !$('heardOn').checked || omniSpokeAt >= lastUserTurnAt || omniTurnOpen) return;
        onOperatorTurnEnd('', false, 'no_reply');
    }, NO_REPLY_S * 1000);
}
async function onOperatorTurnEnd(text, forced = false, reason = 'turn_end', preset = null) {
    let calls = [];
    const seqSeen = preset ? preset.seq : (hud.fsm.seq || 0);   // se la FSM cambia mentre σ pensa, il verdetto e' stantio: il gateway lo scarta
    if (sigmaBusy && reason === 'no_reply') return;
    try {
        if (preset) {
            calls = preset.calls;   // turno TAGLIATO da σ in corsa: il verdetto e' gia' stato dato sul testo parziale
            hudLog('warn', `turno tagliato dopo ${preset.turnS} s: verdetto di σ in corsa al semaforo (${(preset.calls[0].arguments || {}).kind || ''})`);
        } else if ($('heardOn').checked) {
            sigmaBusy = true;
            const t0 = performance.now();
            const timing = { since_user_s: lastUserTurnAt >= 0 ? +(now() - lastUserTurnAt).toFixed(1) : null,
                             since_omni_s: lastOmniEndAt >= 0 ? +(now() - lastOmniEndAt).toFixed(1) : null, omni_speaking: omniTurnOpen };
            const r = await fetch('/api/tool_agent/sigma', { method: 'POST', headers: { 'content-type': 'application/json' },
                body: JSON.stringify({ operator_text: text, fsm: hud.fsm, transcript: dialog.slice(-40), screen: hud.lastText || '', reason, timing, previous_help: lastHelp }) });
            const d = await r.json();
            const dt = ((performance.now() - t0) / 1000).toFixed(2);
            sigmaBusy = false;
            if (r.ok) {
                calls = d.tool_calls || [];
                const a = calls.length ? (calls[0].arguments || {}) : null;
                if (a && forced) {   // turno forzato non informato: i readback possono essere inventati -> restano claim e verdetto
                    for (const k of ['month', 'day', 'time']) delete a[k];
                    hudLog('sys', 'turno FORZATO non informato: readback ignorati');
                }
                if (a) hudLog(a.status === 'stuck' ? 'warn' : 'hud', `σ (${dt} s, ${reason}): ${a.status === 'stuck' ? 'STUCK ' + (a.kind || '') + (a.help ? ' → "' + a.help + '"' : '') : 'ok'}` +
                    `${a.claim ? ' · claim ' + a.claim + (a.claim_time ? ' ' + a.claim_time : '') + (a.claim_day ? ' giorno ' + a.claim_day : '') : ''}` +
                    `${(a.month || a.day || a.time) ? ' · readback ' + JSON.stringify({ month: a.month, day: a.day, time: a.time }) : ''}`);
                else hudLog('sys', `σ (${dt} s): nessun verdetto`);
            } else hudLog('warn', `σ: ${d.error || r.status}`);
        } else if (reason === 'no_reply') return;
        dbg.sigma = { t: now(), reason, a: calls.length ? Object.assign({}, calls[0].arguments || {}) : null, text: text || '' }; renderGraph();
        const r2 = await fetch('/api/hud_fsm/omni_turn', { method: 'POST', headers: { 'content-type': 'application/json' },
            body: JSON.stringify({ text, tool_calls: calls, outcome: $('qOutcome').value, source: 'σ (turno omni)', fsm_seq: seqSeen, reason }) });
        const d2 = await r2.json();
        if (!r2.ok) { hudLog('warn', `semaforo: ${d2.error || r2.status}`); return; }
        if (d2.stale) { hudLog('sys', 'σ: verdetto stantio scartato (la FSM e\' cambiata durante il giudizio)'); return; }
        dbg.verdict = { t: now(), reason, level: d2.level, hint: d2.hint || '', stuck: !!d2.stuck, kind: d2.kind || '', owed: d2.owed || '', capped: !!d2.capped, force: !!d2.force };
        hudLog(d2.level === 'green' ? 'sys' : 'warn', `SEMAFORO ${d2.level.toUpperCase()}${d2.hint ? ' · ' + d2.hint : ''} — "${(text || '(silenzio)').slice(0, 60)}"`);
        applyFsm(d2.fsm, 0);
        conv('sys', stateLine(`turno omni giudicato: ${d2.level}${d2.hint ? ' ' + d2.hint : ''}`));
        if (d2.capped) hudLog('warn', 'σ: tetto di due aiuti per stato raggiunto, nessun altro force finche\' lo stato non cambia');
        lastHelp = (d2.stuck && d2.hint) ? d2.hint : (d2.level === 'red' ? d2.hint : '');
        if (d2.force && !omniTurnOpen) {
            if (forcesSinceUser >= 1) hudLog('sys', `σ chiede aiuto (${d2.kind || d2.level}) ma un aiuto e' gia' stato dato: tocca al cliente`);
            else if (now() - lastForceAt < 6) hudLog('sys', 'σ chiede aiuto ma l\'ultimo force e\' di meno di 6 s fa: niente');
            else { forceSpeakOnce = true; forcesSinceUser++; lastForceAt = now(); hudLog('warn', `σ chiede aiuto (${d2.kind || d2.level}): force_speak col prossimo chunk, che porta lo schermo nuovo`); }
        }
    } catch (e) { sigmaBusy = false; hudLog('warn', 'turno omni errore: ' + e.message); }
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
// ramo force-speak: un turno di parlato a comando. Il flag viene consumato dal prossimo chunk audio (entro 1 s).
let forceSpeakOnce = false, cueOnce = false, cueSamples = null, forceSpeakSentAt = -1, omniSpokeAt = -1;
// politica del turno τ (07/09): force sul frame EVENTO a turno chiuso; se il turno e' aperto il force resta ARMATO (latch) e scatta
// al primo chunk con turno chiuso; guardiano a 3,5 s dopo una tua battuta senza risposta; hold (force_listen dalla pausa alla
// decisione) come opzione spenta. Tetti: pausa 3 s, max 2 forzature per stato, mai nei primi 3 chunk.
const FORCE_COOLDOWN_S = 3, SILENCE_S = 4, HOLD_MAX_CHUNKS = 3;
let lastUserWords = 0;
let omniTurnOpen = false, lastUserTurnAt = -1, lastForceAt = -100, forceCount = {}, forceLatched = false, latchReason = '',
    silenceTimer = null, holdActive = false, holdChunks = 0;
function canForceNow(turns, sess) {
    return !omniTurnOpen && !(turns && turns.speaking) && (sess.chunksSent + 1) >= 4 && (now() - lastForceAt) >= FORCE_COOLDOWN_S && (forceCount[hud.fsm.seq || 0] || 0) < 2;
}
function armSilenceWatchdog() {
    clearTimeout(silenceTimer);
    silenceTimer = setTimeout(() => {
        if (omniSpokeAt >= lastUserTurnAt || !session || !$('autoForce').checked) return;
        forceLatched = true; latchReason = 'guardiano';
        hudLog('warn', `SILENZIO: nessuna risposta entro ${SILENCE_S} s dalla tua battuta → force armato`);
    }, SILENCE_S * 1000);
}
// regione sticky di sistema (ramo forcespeak-stickyctx): schermo + istruzione temporanea del force
let pendingContext = false, instructionActive = '', instructionTimer = null;
function composeContext() {
    const parts = [];
    if ($('stickyScreen').checked && hud.lastText) parts.push('operator screen now: ' + hud.lastText);
    if (instructionActive) parts.push(instructionActive);
    return parts.join('\n');
}
function clearInstruction(why) {
    if (!instructionActive) return;
    instructionActive = ''; clearTimeout(instructionTimer); pendingContext = true;
    hudLog('sys', `istruzione rimossa dalla regione di sistema (${why})`);
}
/** Testo da iniettare col force_speak: vuoto = solo force; {screen} = testo dello schermo. */
function injectTextNow() { const t = ($('injectText').value || '').trim(); return t ? t.replace(/\{screen\}/g, hud.lastText || '') : ''; }
$('btnForceSpeak').onclick = () => { forceSpeakOnce = true; hudLog('warn', 'FORCE_SPEAK richiesto: parte col prossimo chunk'); };
$('btnCue').onclick = async () => {
    if (!cueSamples) {
        try {
            const r = await fetch('/static/hud/cues/cue.wav', { cache: 'no-store' });
            if (!r.ok) throw new Error('HTTP ' + r.status);
            const ac = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: SR_IN });
            const buf = await ac.decodeAudioData(await r.arrayBuffer());
            cueSamples = buf.getChannelData(0).slice(0, SR_IN);   // al massimo 1 s = un chunk
            hudLog('sys', `clip stimolo caricato: ${(buf.duration).toFixed(2)} s`);
        } catch (e) { hudLog('warn', 'stimolo audio: manca static/hud/cues/cue.wav (' + e.message + ')'); return; }
    }
    cueOnce = true; hudLog('warn', 'STIMOLO AUDIO richiesto: parte col prossimo chunk al posto del microfono');
};
// ---- GRAFO DELLA MACCHINA (13/09, Alessandro: "una sezione che mi mostri graficamente lo stato in cui ci troviamo, con grafi e frecce").
//      Solo visualizzazione: legge lo stato che il client ha gia' (hud.fsm, verdetti di σ, esiti del semaforo, force, tempi). Nessun
//      effetto sul frame, sul canale testuale o sulla FSM. Nodo colorato = stato attuale col colore del semaforo; freccia arancione =
//      ultimo passaggio (con l'evento che l'ha causato); accanto i meccanismi: semaforo, risultato dovuto, σ, force (cooldown e tetti),
//      cliente, omni. Si aggiorna a ogni evento e ogni mezzo secondo (contatori).
const dbg = { prev: null, edge: null, event: null, sigma: null, verdict: null, force: null };
let userTurns = 0;   // (grafo) battute del cliente contate qui: su questo ramo il gateway non le riceve
const dbgEsc = (x) => String(x ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const dbgAgo = (t) => `${Math.max(0, now() - t).toFixed(1)} s fa`;
const dbgCut = (x, n) => { x = String(x || ''); return x.length > n ? x.slice(0, n - 1) + '…' : x; };
function dbgEdgeLabel() {
    const t = now();
    if (dbg.event && t - dbg.event.t < 4) return dbg.event.calls.map(c => c.name + (Object.keys(c.arguments || {}).length ? '(' + Object.entries(c.arguments).map(([k, v]) => `${k}=${v}`).join(', ') + ')' : '')).join(' ');
    if (dbg.sigma && t - dbg.sigma.t < 4 && dbg.sigma.a) { const a = dbg.sigma.a; return a.claim ? `σ: ${a.claim}${a.claim_day ? ' g.' + a.claim_day : ''}${a.claim_time ? ' ' + a.claim_time : ''}` : 'σ'; }
    return '';
}
function dbgFsm(prev, cur) {
    if (!dbg.booted) { dbg.booted = true; renderGraph(); return; }   // primo stato letto al caricamento: non e' un passaggio
    if (prev && ((prev.seq || 0) !== (cur.seq || 0) || prev.state !== cur.state || prev.status !== cur.status)) {
        dbg.prev = prev; dbg.edge = { from: prev.state, to: cur.state, t: now(), label: dbgEdgeLabel() };
    }
    renderGraph();
}
const GN = { IDLE: { x: 6, y: 88, w: 90, h: 84 }, COLLECTING: { x: 160, y: 80, w: 140, h: 100 }, CONFIRM: { x: 368, y: 80, w: 130, h: 100 }, DONE: { x: 560, y: 88, w: 74, h: 84 } };
const NODE_FILL = { green: ['#e8f5e9', '#2e7d32'], yellow: ['#fff8e1', '#f9a825'], red: ['#ffebee', '#c62828'] };
function dbgAnchor(r, tx, ty) {
    const cx = r.x + r.w / 2, cy = r.y + r.h / 2, dx = tx - cx, dy = ty - cy;
    const sx = Math.abs(dx) > 1e-6 ? (r.w / 2) / Math.abs(dx) : Infinity, sy = Math.abs(dy) > 1e-6 ? (r.h / 2) / Math.abs(dy) : Infinity;
    const k = Math.min(sx, sy, 1); return [cx + dx * k, cy + dy * k];
}
function dbgNodeLines(st, f, cur) {
    if (!cur) return [st, '', { IDLE: 'BOOKING DESK', COLLECTING: 'raccolta: cosa manca', CONFIRM: 'domanda sì / no aperta', DONE: 'BOOKED / TAKEN' }[st] || ''];
    const sl = f.slots || {}, tent = f.tentative || {};
    const when = [(sl.month || '').toUpperCase(), sl.day || ''].filter(Boolean).join(' ') + (sl.time && sl.time !== 'all-day' ? ', ' + timeLabel(sl.time) : (sl.time === 'all-day' && sl.day ? ', ALL DAY' : ''));
    const marks = Object.keys(tent).filter(k => tent[k]).map(k => k + (tent[k] === 'proposal' ? '?' : '~')).join(' ');
    if (st === 'IDLE') return ['IDLE', 'BOOKING DESK', f.note || ''];
    if (st === 'COLLECTING') return ['COLLECTING', (f.intent === 'check' ? 'FREE: ' : 'BOOK: ') + (when || '?'),
        [(f.month_info ? 'lista del mese' : ''), ((f.missing || []).length ? 'manca ' + f.missing.join(', ') : ''), marks ? 'tentativi ' + marks : '', (f.pick || []).length ? 'pick ' + f.pick.join(',') : ''].filter(Boolean).join(' · ')];
    if (st === 'CONFIRM') return ['CONFIRM', when || '?', (f.intent === 'book' ? 'FREE · SHALL I BOOK IT?' : (f.status === 'partial' ? 'FREE, EXCEPT ' + takenList(f.detail).join(', ') : 'FREE · ' + (sl.time && sl.time !== 'all-day' ? 'SHALL I BOOK IT?' : 'WHAT TIME?'))) + (marks ? ' · ' + marks : '')];
    const stl = f.status === 'confirmed' ? 'BOOKED' : ((f.status === 'taken' || f.status === 'booked') ? 'TAKEN' : (f.status === 'error' ? 'ERROR' : 'chiusa'));
    return ['DONE · ' + stl, when || '?', f.status === 'confirmed' ? 'ANYTHING ELSE?' : ((f.status === 'taken' || f.status === 'booked') ? 'ANOTHER TIME?' : (f.status || ''))];
}
function renderGraph() {
    const svg = $('fsmGraph'), mech = $('mech'); if (!svg || !mech) return;
    const f = hud.fsm, t = now(), lvl = f.level || 'green', cur = f.state || 'IDLE';
    const showEdge = dbg.edge && t - dbg.edge.t < 20;
    const out = [`<defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#90a4ae"/></marker>` +
                 `<marker id="arrO" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#fb8c00"/></marker></defs>`];
    const labels = [];
    const lab = (x, y, s, cls = 'lab') => labels.push(`<text class="${cls}" x="${x}" y="${y}" text-anchor="middle">${dbgEsc(s)}</text>`);
    const line = (x1, y1, x2, y2, s, dy = -6) => { out.push(`<path class="edge" d="M${x1},${y1} L${x2},${y2}" marker-end="url(#arr)"/>`); if (s) lab((x1 + x2) / 2, Math.min(y1, y2) + dy, s); };
    const curve = (x1, y1, x2, y2, depth, s, dash = false) => { const cx = (x1 + x2) / 2, cy = (y1 + y2) / 2 + depth * 2; out.push(`<path class="edge${dash ? ' dash' : ''}" d="M${x1},${y1} Q${cx},${cy} ${x2},${y2}" marker-end="url(#arr)"/>`); if (s) lab(cx, (y1 + y2) / 2 + depth + (depth > 0 ? 12 : -6), s); };
    const loop = (r, s) => { const cx = r.x + r.w / 2, y = r.y; out.push(`<path class="edge" d="M${cx - 16},${y} C${cx - 34},${y - 46} ${cx + 34},${y - 46} ${cx + 16},${y}" marker-end="url(#arr)"/>`); lab(cx, y - 44, s); };
    const I = GN.IDLE, C = GN.COLLECTING, K = GN.CONFIRM, D = GN.DONE, mid = (r) => r.y + r.h / 2;
    // frecce fisse (la macchina: gateway.py _hud_fsm_apply)
    line(I.x + I.w, mid(I) - 4, C.x, mid(C) - 4, 'set');
    line(C.x + C.w, mid(C) - 4, K.x, mid(K) - 4, 'completo');
    line(K.x + K.w, mid(K) - 4, D.x, mid(D) - 4, 'yes: scrive');
    curve(K.x + 30, K.y + K.h, C.x + C.w - 30, C.y + C.h, 40, 'no · valore nuovo → si torna a chiedere');
    curve(C.x + C.w / 2, C.y + C.h, D.x + D.w / 2 - 10, D.y + D.h, 75, 'set completo su uno slot occupato → TAKEN');
    curve(D.x + D.w / 2 + 14, D.y + D.h, C.x + 30, C.y + C.h, 100, 'nuova richiesta (set) → raccolta');
    curve(C.x + 30, C.y, I.x + I.w / 2 + 10, I.y, -30, 'cancel → IDLE', true);
    loop(C, 'set · readback · proposta · pick');
    loop(K, 'no con pick → prossimo libero');
    lab(D.x + D.w / 2, D.y + D.h + 14, 'cancel: ignorato');
    // nodi
    for (const st of ['IDLE', 'COLLECTING', 'CONFIRM', 'DONE']) {
        const r = GN[st], isCur = st === cur, isPrev = showEdge && dbg.edge.from === st && !isCur;
        const [fill, stroke] = isCur ? NODE_FILL[lvl] || NODE_FILL.green : ['#fff', isPrev ? '#78909c' : '#cfd8dc'];
        out.push(`<rect x="${r.x}" y="${r.y}" width="${r.w}" height="${r.h}" rx="10" fill="${fill}" stroke="${stroke}" stroke-width="${isCur ? 3 : 1.5}"${isPrev ? ' stroke-dasharray="4 3"' : ''}/>`);
        const [l1, l2, l3] = dbgNodeLines(st, f, isCur), cx = r.x + r.w / 2, maxc = Math.floor(r.w / 6.2);
        out.push(`<text x="${cx}" y="${r.y + 22}" text-anchor="middle" font-size="13" font-weight="700" fill="${isCur ? '#1f2933' : '#607d8b'}">${dbgEsc(l1)}</text>`);
        if (l2) out.push(`<text x="${cx}" y="${r.y + 44}" text-anchor="middle" font-size="12" fill="#1f2933">${dbgEsc(dbgCut(l2, maxc))}</text>`);
        if (l3) out.push(`<text x="${cx}" y="${r.y + 63}" text-anchor="middle" font-size="10" fill="#546e7a">${dbgEsc(dbgCut(l3, Math.floor(r.w / 5.2)))}</text>`);
    }
    // ultimo passaggio
    if (showEdge) {
        const a = GN[dbg.edge.from] || GN.IDLE, b = GN[dbg.edge.to] || GN.IDLE;
        if (dbg.edge.from === dbg.edge.to) {
            out.push(`<rect class="last" x="${b.x - 6}" y="${b.y - 6}" width="${b.w + 12}" height="${b.h + 12}" rx="14"/>`);
            lab(320, 13, dbgCut(`ultimo passaggio: ${dbg.edge.to} aggiornato ↻${dbg.edge.label ? ' · ' + dbg.edge.label : ''}`, 90), 'lastlab');
        } else {
            const [x1, y1] = dbgAnchor(a, b.x + b.w / 2, b.y + b.h / 2), [x2, y2] = dbgAnchor(b, a.x + a.w / 2, a.y + a.h / 2);
            out.push(`<path class="last" d="M${x1},${y1} L${x2},${y2}" marker-end="url(#arrO)"/>`);
            lab(320, 13, dbgCut(`ultimo passaggio: ${dbg.edge.from} → ${dbg.edge.to}${dbg.edge.label ? ' · ' + dbg.edge.label : ''}`, 90), 'lastlab');
        }
    }
    svg.innerHTML = out.concat(labels).join('');
    // meccanismi
    const chip = (txt, col) => `<span class="chip" style="background:${col}">${dbgEsc(txt)}</span>`;
    const rows = [];
    rows.push(['Semaforo', chip(lvl.toUpperCase(), LIGHT[lvl] || '#2e7d32') + ' ' + dbgEsc(f.hint || (lvl === 'green' ? 'OK' : '')) + ` <span class="mute">· seq ${f.seq || 0}</span>`]);
    const ro = f.result_owed;
    if (ro !== undefined) rows.push(['Risultato dovuto', ro ? (ro.forced ? chip('FORZATO 1 volta', '#f9a825') + ' <span class="mute">per questo schermo, poi tocca a σ</span>'
                                             : chip('DOVUTO', '#1a237e') + ' <span class="mute">il prossimo turno deve dirlo (lo giudica σ: screen_said)</span>')
                                     : '<span class="mute">nessuno: detto, oppure schermo senza risultato</span>']);
    const sg = dbg.sigma, a = sg && sg.a;
    rows.push(['σ (ultimo verdetto)', sg ? `<span class="mute">${dbgAgo(sg.t)} · ${dbgEsc(sg.reason)}${sg.turnS ? ' a ' + sg.turnS + ' s' : ''}</span> ` +
        (a ? ((a.status === 'stuck' ? chip('STUCK ' + (a.kind || ''), '#c62828') + (a.help ? ' “' + dbgEsc(a.help) + '”' : '') : chip('ok', '#2e7d32')) +
              (a.claim ? ` · claim ${dbgEsc(a.claim)}${a.claim_time ? ' ' + dbgEsc(a.claim_time) : ''}${a.claim_day ? ' g.' + dbgEsc(a.claim_day) : ''}` : '') +
              (a.screen_said ? ` · risultato detto <b>${dbgEsc(a.screen_said)}</b>` : '') +
              ((a.month || a.day || a.time) ? ` · readback ${dbgEsc([a.month, a.day, a.time].filter(Boolean).join(' '))}` : ''))
           : '<span class="mute">nessun verdetto</span>') + (sigmaBusy ? ' ' + chip('sta giudicando…', '#6b7280') : '') : '<span class="mute">—</span>' + (sigmaBusy ? ' ' + chip('sta giudicando…', '#6b7280') : '')]);
    const v = dbg.verdict;
    rows.push(['Esito del turno', v ? `<span class="mute">${dbgAgo(v.t)}</span> ` + chip(v.level.toUpperCase(), LIGHT[v.level] || '#2e7d32') + (v.hint ? ' ' + dbgEsc(v.hint) : '') +
        (v.owed ? ' ' + chip('RISULTATO NON DETTO', '#f9a825') : '') + (v.stuck ? ' · stuck ' + dbgEsc(v.kind) : '') + (v.capped ? ' ' + chip('TETTO', '#6b7280') : '') +
        (v.force ? ' → <b>force</b>' : ' → nessun force') : '<span class="mute">—</span>']);
    const cd = Math.max(0, 6 - (t - lastForceAt)), fo = dbg.force;
    rows.push(['Force', (fo ? `<span class="mute">${dbgAgo(fo.t)}</span> ${dbgEsc(fo.why)} · chunk #${fo.chunk}` : '<span class="mute">nessuno</span>') +
        ` · cooldown ${cd > 0 ? chip(cd.toFixed(1) + ' s', '#6b7280') : 'libero'} · aiuti dopo la tua battuta <b>${forcesSinceUser}</b>/1 · tetto per stato <b>${f.stuck_count || 0}</b>/2 · tagli <b>${cutsSinceUser}</b>/${MAX_CUTS_PER_USER_TURN}` +
        (omniTurnOpen ? ' · <span class="mute">turno aperto: nessun force</span>' : '')]);
    const e = dbg.event;
    rows.push(['Cliente', `battute <b>${userTurns}</b>` + (lastUserTurnAt >= 0 ? ` <span class="mute">(ultima ${dbgAgo(lastUserTurnAt)})</span>` : '') +
        (userLines.length ? ` · ASR “${dbgEsc(dbgCut(userLines[userLines.length - 1], 70))}”` : '') +
        (e ? ` · evento ${dbgEsc(e.calls.map(c => c.name + JSON.stringify(c.arguments || {})).join(' '))} ${e.changed ? chip('macchina cambiata', '#2e7d32') : chip('invariata', '#6b7280')}` : '')]);
    rows.push(['Omni', (omniTurnOpen ? chip('TURNO APERTO ' + Math.max(0, t - omniSpokeAt).toFixed(0) + ' s', '#fb8c00') : chip('in ascolto', '#6b7280')) +
        (lastOmniEndAt >= 0 && !omniTurnOpen ? ` <span class="mute">ultimo turno chiuso ${dbgAgo(lastOmniEndAt)}</span>` : '') +
        (currentAiText ? ` · “…${dbgEsc(currentAiText.slice(-80))}”` : '')]);
    mech.innerHTML = rows.map(([k, val]) => `<div class="mk">${k}</div><div class="mv">${val}</div>`).join('');
}
setInterval(() => { try { renderGraph(); } catch (_) { /* il grafo non deve mai rompere la pagina */ } }, 500);

$('btnQuery').onclick = manualRequest;
$('btnReset').onclick = fsmReset;
$('btnFrame').onclick = () => hudSync(true);
drawHud();
renderGraph();   // grafo di debug: disegnato subito, poi a ogni evento
checkToolAgent();
fetch('/api/hud_fsm').then(r => r.json()).then(f => applyFsm(f, 0)).catch(() => {});   // stato corrente della FSM (db.html lo vede uguale)
