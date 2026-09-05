import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, KeepTogether
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from PIL import Image as PILImage

S = "/tmp/claude-1000/-home-alex-progetti-MiniCPM-o-Demo/f961457c-85a6-44a5-a2a1-96bdcf75b1aa/scratchpad"
OUT = "/home/alex/progetti/MiniCPM-o-Demo/docs/architettura-hud-algebra.pdf"
pdfmetrics.registerFont(TTFont("DV", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DVB", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DVI", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"))
pdfmetrics.registerFont(TTFont("DVM", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"))
registerFontFamily("DV", normal="DV", bold="DVB", italic="DVI", boldItalic="DVB")

ss = getSampleStyleSheet()
NAVY = colors.HexColor("#1a237e")
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="DVB", fontSize=16, spaceBefore=12, spaceAfter=6, textColor=NAVY)
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="DVB", fontSize=12, spaceBefore=8, spaceAfter=4, textColor=colors.HexColor("#283593"))
P = ParagraphStyle("P", parent=ss["BodyText"], fontName="DV", fontSize=9.6, leading=13.6, spaceAfter=5)
PS = ParagraphStyle("PS", parent=P, fontSize=8.4, leading=11.2, textColor=colors.HexColor("#455a64"))
CAP = ParagraphStyle("CAP", parent=P, fontName="DVI", fontSize=8.2, leading=10.5, textColor=colors.HexColor("#546e7a"), spaceAfter=8)
BUL = ParagraphStyle("BUL", parent=P, leftIndent=12, bulletIndent=2)
MONO = ParagraphStyle("MONO", parent=P, fontName="DVM", fontSize=8.6, leading=12, backColor=colors.HexColor("#f3f4f6"), borderPadding=5, leftIndent=4, spaceAfter=8)
TITLE = ParagraphStyle("T", parent=ss["Title"], fontName="DVB", fontSize=22, leading=28, textColor=NAVY)
SUB = ParagraphStyle("SUB", parent=P, fontSize=11.5, leading=15.5, textColor=colors.HexColor("#37474f"))
TH = ParagraphStyle("TH", parent=P, fontName="DVB", fontSize=8.4, leading=10.5, textColor=colors.white)
TD = ParagraphStyle("TD", parent=P, fontSize=8.4, leading=10.8, spaceAfter=0)


def img(path, width_cm):
    w, h = PILImage.open(path).size
    return Image(path, width=width_cm * cm, height=width_cm * cm * h / w)


def table(rows, widths, header=True):
    data = [[Paragraph(c, TH if (header and i == 0) else TD) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1 if header else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cfd8dc")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if header:
        st += [("BACKGROUND", (0, 0), (-1, 0), NAVY)]
    for i in range(1, len(rows)):
        if i % 2 == 0:
            st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f5f7fa")))
    t.setStyle(TableStyle(st))
    return t


# ---------------------------------------------------------------- figure 1: l'algebra
def box(ax, x, y, w, h, text, fc, fs=9.5, tc="white", bold=True):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.03", fc=fc, ec="none"))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=tc, weight="bold" if bold else "normal", linespacing=1.35)


def arrow(ax, p, q, text="", color="#37474f", ls="-", off=(0, 0.02)):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=14, lw=1.6, color=color, linestyle=ls, shrinkA=2, shrinkB=2))
    if text:
        ax.text((p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1], text, ha="center", va="bottom", fontsize=7.8, color=color)


fig, ax = plt.subplots(figsize=(11, 5.6)); ax.set_xlim(0, 11); ax.set_ylim(0, 5.6); ax.axis("off")
box(ax, 0.3, 2.2, 1.7, 1.3, "UTENTE\n(voce)", "#37474f")
box(ax, 3.2, 3.9, 2.4, 1.3, "OMNI\nMiniCPM-o 4.5\nascolta / parla", "#1a237e")
box(ax, 3.2, 0.4, 2.4, 1.3, "ε  estrattore\n(atto aperto, battuta) → E", "#6a1b9a")
box(ax, 6.4, 0.4, 2.2, 1.3, "δ  macchina\n(R, E) → (R', atto)", "#2e7d32")
box(ax, 9.0, 0.4, 1.8, 1.3, "R  record\n+ DB", "#00695c")
box(ax, 6.4, 3.9, 2.2, 1.3, "ρ  resa\n(atto, R) → frame", "#ef6c00")
arrow(ax, (2.0, 3.2), (3.2, 4.4), "audio 16 kHz", "#1a237e", off=(-0.25, 0.05))
arrow(ax, (3.2, 4.2), (2.0, 2.9), "voce", "#1a237e", off=(-0.35, -0.2))
arrow(ax, (2.0, 2.5), (3.2, 1.2), "ASR (secondo orecchio)", "#6a1b9a", off=(0.05, -0.32))
arrow(ax, (5.6, 1.05), (6.4, 1.05), "evento E", "#2e7d32")
arrow(ax, (8.6, 1.05), (9.0, 1.05), "", "#00695c")
arrow(ax, (7.5, 1.7), (7.5, 3.9), "atto + R", "#ef6c00", off=(0.45, 0))
arrow(ax, (6.4, 4.55), (5.6, 4.55), "frame 1 Hz (64 token)", "#ef6c00", off=(0, 0.06))
arrow(ax, (7.5, 1.7), (4.6, 1.7), "", "#6a1b9a", ls="--")
ax.text(6.0, 1.86, "atto aperto (domanda in corso)", ha="center", fontsize=7.8, color="#6a1b9a")
ax.text(5.5, 5.42, "canale nativo: l'omni sente e parla", ha="center", fontsize=8.5, color="#1a237e", style="italic")
ax.text(5.5, 0.12, "canale laterale deterministico: un solo LLM (ε), il resto è codice", ha="center", fontsize=8.5, color="#2e7d32", style="italic")
plt.savefig(f"{S}/arch_fig1.png", dpi=170, bbox_inches="tight"); plt.close()

# ---------------------------------------------------------------- figure 2: il frame a due metà
fig, axs = plt.subplots(1, 4, figsize=(11, 3.1))
frames = [("#1565c0", "ASK: DAY", "APRIL ?  ·  15:00", "manca il giorno"),
          ("#2e7d32", "SAY: AVAILABLE", "APRIL 4  ALL DAY", "offerta in sospeso"),
          ("#1b5e20", "ASK: CONFIRM", "BOOK APRIL 4 15:00?", "conferma"),
          ("#c62828", "SAY: SLOT TAKEN", "APRIL 4  15:00", "esito")]
for ax, (c, top, bottom, cap) in zip(axs, frames):
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.add_patch(FancyBboxPatch((0.02, 0.05), 0.96, 0.9, boxstyle="round,pad=0.01,rounding_size=0.03", fc=c, ec="none"))
    ax.plot([0.08, 0.92], [0.5, 0.5], color="white", lw=1.2, alpha=0.7)
    ax.text(0.5, 0.74, top, ha="center", va="center", fontsize=12.5, color="white", weight="bold")
    ax.text(0.5, 0.29, bottom, ha="center", va="center", fontsize=9.5, color="white")
    ax.text(0.5, 0.0, cap, ha="center", va="top", fontsize=8, color="#546e7a", style="italic")
plt.savefig(f"{S}/arch_fig2.png", dpi=170, bbox_inches="tight"); plt.close()

# ---------------------------------------------------------------- figure 3: oggi vs streaming vs omni nativo
fig, ax = plt.subplots(figsize=(11, 4.0)); ax.set_xlim(-0.2, 11); ax.set_ylim(0, 3.4); ax.axis("off")
def lane(y, label):
    ax.text(-0.15, y + 0.28, label, ha="right", va="center", fontsize=8.8, weight="bold", color="#263238")
    ax.plot([0, 10.8], [y, y], color="#b0bec5", lw=1)
def seg(y, a, b, text, c):
    ax.add_patch(FancyBboxPatch((a, y + 0.06), b - a, 0.44, boxstyle="round,pad=0.01,rounding_size=0.02", fc=c, ec="none"))
    ax.text((a + b) / 2, y + 0.28, text, ha="center", va="center", fontsize=7.8, color="white", weight="bold")
for x in range(0, 11):
    ax.text(x, 3.15, f"{x}s", ha="center", fontsize=7, color="#78909c"); ax.plot([x, x], [0.2, 3.05], color="#eceff1", lw=0.8, zorder=0)
lane(2.3, "oggi"); seg(2.3, 0, 2.6, "utente parla", "#37474f"); seg(2.3, 2.6, 3.2, "VAD", "#78909c"); seg(2.3, 3.2, 3.4, "ASR", "#6a1b9a"); seg(2.3, 3.4, 4.4, "ε cloud ~1 s", "#6a1b9a"); seg(2.3, 4.4, 5.4, "frame (chunk)", "#ef6c00"); seg(2.3, 5.4, 6.2, "omni legge", "#1a237e")
ax.text(3.6, 2.85, "l'omni può aprire bocca qui ↓ (1-2 s dopo la fine)", fontsize=7.4, color="#1a237e")
lane(1.35, "ASR streaming"); seg(1.35, 0, 2.6, "utente parla", "#37474f"); seg(1.35, 0.8, 2.9, "ASR+ε incrementali (idempotenti)", "#6a1b9a"); seg(1.35, 2.9, 3.6, "frame", "#ef6c00"); seg(1.35, 3.6, 4.4, "omni legge", "#1a237e")
lane(0.4, "omni nativo"); seg(0.4, 0, 2.6, "utente parla", "#37474f"); seg(0.4, 2.6, 2.75, "⟨evento⟩", "#6a1b9a"); seg(0.4, 2.75, 3.0, "δ", "#2e7d32"); seg(0.4, 3.0, 3.8, "frame", "#ef6c00")
ax.text(4.2, 0.62, "l'evento nasce dallo stesso contesto che ha sentito tutto: niente ASR, niente VAD, niente corsa", fontsize=7.6, color="#2e7d32")
plt.savefig(f"{S}/arch_fig3.png", dpi=170, bbox_inches="tight"); plt.close()

# ---------------------------------------------------------------- documento
doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=1.9 * cm, rightMargin=1.9 * cm, topMargin=1.7 * cm, bottomMargin=1.6 * cm,
                        title="Architettura teorica: HUD come linguaggio, eventi come algebra", author="Alessandro / Claude")
E = []
E += [Paragraph("Assistente vocale con logica di dominio esterna", TITLE),
      Paragraph("L'HUD come linguaggio, gli eventi come algebra: architettura teorica, mappa del sistema attuale, cosa cambierebbe davvero", SUB),
      Spacer(1, 4), Paragraph("Progetto MiniCPM-o-Demo (ramo HUD) · 05/09/2026 · sintesi di tre giorni di misure (plan/ramo-hud.md, analisi-toolcalling.md)", PS), Spacer(1, 8)]

E += [Paragraph("1. Il problema in una riga", H1),
      Paragraph("Un modello vocale end-to-end (MiniCPM-o 4.5: ascolta e parla in full-duplex, 1 unità al secondo) non emette chiamate di funzione e non "
                "ha un ingresso testuale in tempo reale. L'unico canale laterale che ha è la <b>visione</b>: un fotogramma per unità, 64 token. "
                "La logica di dominio (prenotazioni, DB, regole) deve quindi vivere <b>fuori</b> dal modello, e comunicare con lui attraverso "
                "un'immagine. Il resto dell'architettura discende da questo vincolo.", P)]

E += [Paragraph("2. L'algebra", H1),
      Paragraph("Tre oggetti e tre funzioni. Tutto ciò che è di dominio sta in un solo posto (la macchina δ); il modello che parla non conosce regole.", P),
      img(f"{S}/arch_fig1.png", 16.5), Paragraph("Figura 1 · Il ciclo: l'utente è sentito due volte (canale nativo dell'omni; secondo orecchio ASR → ε); la macchina δ produce un atto e un record; la resa ρ li disegna nel frame che l'omni legge.", CAP)]
E += [Paragraph("2.1 Gli oggetti", H2),
      Paragraph("<b>R, il record.</b> Uno schema tipato di slot con validatori. L'<b>intento è uno slot</b> come gli altri (verifica / prenotazione / …): "
                "non esistono funzioni per dominio. Il compito è finito quando gli slot richiesti dall'intento sono validi e l'azione è stata eseguita.", P),
      Paragraph("<b>E, gli eventi.</b> Tutto ciò che un utente può fare a un record, e nient'altro:", P)]
for b in ["<b>Set(slot, valore)</b> — fornire o correggere un valore, anche fuori turno, anche più di uno per battuta",
          "<b>Answer(sì | no)</b> — rispondere alla domanda aperta",
          "<b>Choose(opzione)</b> — scegliere tra le opzioni proposte",
          "<b>Abort</b> — lasciar perdere",
          "<b>Nothing</b> — saluti, esitazioni, chiacchiere"]:
    E.append(Paragraph(b, BUL, bulletText="•"))
E += [Paragraph("<b>A, gli atti.</b> Le domande che la macchina può porre, al più una aperta alla volta: <b>ASK(slot)</b>, <b>OFFER(opzioni)</b>, "
                "<b>CONFIRM(record)</b>, <b>TELL(esito)</b>, <b>NONE</b>.", P),
      Paragraph("2.2 Le funzioni", H2),
      Paragraph("<b>ε, l'estrattore</b>: (atto aperto, battuta) → E. Interpreta la battuta <i>relativamente alla domanda aperta</i>: dopo ASK(day) un numero è "
                "Set(day); dopo CONFIRM un \"sì\" è Answer(sì); in qualunque momento \"vorrei prenotare\" è Set(intent). È la struttura domanda/risposta "
                "della conversazione. Il modello non deve conoscere lo stato, solo la domanda; e non deve calcolare nulla.", P),
      Paragraph("<b>δ, la macchina</b>: (R, E) → (R', atto). Deterministica e <b>idempotente</b> (lo stesso Set due volte non cambia nulla): merge, validazione, "
                "esecuzione sul DB, scelta del prossimo atto. Tutto il dominio sta qui, in if/else.", P),
      Paragraph("<b>ρ, la resa</b>: (atto, R) → frame. Tabelle, mai un modello. L'omni è l'attore: rende l'atto in voce con il suo tono.", P),
      Paragraph("2.3 Completezza", H2),
      Paragraph("Ogni mossa dell'utente è una risposta alla domanda aperta, una nuova assegnazione, un abbandono, o niente: l'insieme E è chiuso. Ogni compito "
                "esprimibile come <b>modulo più azioni</b> (raccogli valori, eventualmente scegli, conferma, esegui, riferisci) è una δ. Cambiare dominio "
                "significa cambiare R e δ, non E, non A, non ε. Cambiare lingua significa cambiare le parole sul frame. È la tesi dei sistemi a frame "
                "(slot-filling con conferma), la stessa di Rasa: collect, action, branch.", P),
      Paragraph("2.4 Dove non è completo", H2)]
for b in ["<b>Larghezza del canale</b>: 64 token, 448 pixel, tre righe. OFFER regge 2-3 opzioni; liste, testi, condizioni non entrano: vanno ridotti dalla macchina o non esserci.",
          "<b>Un atto per frame</b>: un solo compito in fuoco. Richieste intrecciate vanno serializzate da δ.",
          "<b>Niente calcolo dal lato dell'attore</b>: aritmetica e ricerche sono di δ, e finiscono nello stato. È un limite voluto.",
          "<b>Canale a senso unico</b>: la macchina non sente l'attore, quindi non sa se l'atto è stato eseguito; lo deduce dalla battuta successiva. Tollerante, non garantito.",
          "<b>Niente \"aspetta\"</b>: nessun atto esprime attesa; misurato che produce silenzi. Le attese lunghe si rendono come stato (TELL in corso)."]:
    E.append(Paragraph(b, BUL, bulletText="•"))

E += [Paragraph("3. Il linguaggio dell'HUD", H1),
      Paragraph("Un frame è la quadrupla ⟨ATTO, OGGETTO, STATO, TICK⟩: sopra l'atto (verbo + oggetto, due o tre parole, imperativo, mai \"aspetta\"); sotto lo stato "
                "(il record: pieno, mancante, esito); il tick è il cambio di tonalità dello sfondo che segna ogni evento, perché il canale non ha un \"invia\", ha solo un \"mostra\".", P),
      img(f"{S}/arch_fig2.png", 16.5), Paragraph("Figura 2 · Quattro frame del linguaggio: raccolta, offerta, conferma, esito. Le parole sono generate da tabelle nel codice.", CAP)]
E.append(table([["Invariante", "Perché"],
                ["Un atto per frame", "l'omni legge un'immagine alla volta; due domande = nessuna"],
                ["Oggetto di ≤ 3 parole, maiuscolo", "leggibilità a 448 px; frasi lunghe vengono lette ad alta voce o ignorate"],
                ["Verbi imperativi, mai \"wait\"", "misurato: \"please wait\" → silenzi di 30 s, \"one moment\" → attrattore dell'attesa"],
                ["Stato sempre presente, anche con atto NONE", "è la memoria del compito, esterna al modello e alla sua finestra di contesto"],
                ["Ogni cambio di atto o stato è un tick", "un valore respinto o una conferma ripetuta devono produrre pixel nuovi"],
                ["Parole da tabelle, mai da un modello", "coerenza tra ciò che l'HUD segna e ciò che la macchina fa (regola di Alessandro)"]], [5.2, 11.6]))

E += [PageBreak(), Paragraph("4. Il sistema attuale, mappato sull'algebra", H1),
      Paragraph("La forma è quella dell'algebra, con due compressioni pragmatiche fatte per il modello locale da 1,7B.", P)]
E.append(table([["Oggetto algebrico", "Nel sistema attuale", "Scostamento"],
                ["R, record", "slot month / day / time / intent, validatori nel gateway (mese = nome, giorno 1-31, ora HH:MM), DB in data/hud_db.json", "—"],
                ["E, eventi", "tre strumenti fissi book / check_availability / cancel; nessuna chiamata = Nothing", "il significato cambia con lo stato (\"book senza campi\" = Answer(sì)); la versione con accept/provide era l'algebra pulita (cloud 24/24), tolta per semplicità"],
                ["A, atti", "stati IDLE / COLLECTING / CONFIRM / DONE con MISSING, WAIT FOR USER CONFIRMATION, esiti", "l'atto è implicito nello stato; non c'è ancora la metà \"sopra\" del frame"],
                ["ε, estrattore", "VAD nel browser → Whisper small (GPU) → gemini-3.5-flash-lite via API Cline (locale Qwen3-1.7B come fallback); riga di stato senza valori; ultime 6 righe del dialogo solo sul cloud", "gira a fine turno (VAD), non in streaming: corsa con la risposta dell'omni e frasi spezzate"],
                ["δ, macchina", "_hud_fsm_apply: merge idempotente, campi indipendenti dall'ordine, numero secco = risposta alla domanda corrente, conferma prima di scrivere", "—"],
                ["ρ, resa", "themeFor(): tabella stato → frame; impronta = pixel; sfondo alternato a ogni seq", "—"],
                ["Misure", "regressioni: cloud 51/55 base e 24/24 dialogo (~1 s); locale 47-52/55 e 17/20 (0,5-0,8 s); dal vivo: 6,5 min coerenti con trp 1,0 + finestra KV", ""]], [3.2, 8.2, 5.4]))
E.append(Spacer(1, 6))

E += [Paragraph("5. Cosa cambierebbe davvero", H1),
      img(f"{S}/arch_fig3.png", 16.5), Paragraph("Figura 3 · Linea del tempo dalla fine della frase: oggi il frame arriva ~1,8-2,8 s dopo (l'omni può già aver risposto); con ASR in streaming arriva mentre l'utente finisce; con l'omni che emette gli eventi non c'è più il secondo orecchio.", CAP),
      Paragraph("5.1 Senza toccare l'omni", H2)]
E.append(table([["Intervento", "Cosa risolve", "Costo", "Impatto"],
                ["<b>ASR in streaming + eventi incrementali</b>: la trascrizione cresce, ε gira ogni ~1 s sul testo parziale, δ idempotente assorbe i duplicati; il frame è pronto quando l'utente smette", "la corsa tra frame e risposta dell'omni; il VAD che spezza le frasi (i pezzi diventano Set successivi); il turno perso quando l'estrattore è occupato", "un ASR streaming (Whisper con finestra scorrevole o modello streaming), stessa ε, stessa δ", "grande: è il collo di bottiglia misurato (1,8-2,8 s fine frase → frame)"],
                ["<b>Decodifica vincolata per il locale</b>: grammatica JSON imposta ai token, solo le chiamate valide per l'atto aperto", "formato rotto, campi spazzatura (day='of'), scelta di 'none' su richieste vere", "basso (logits processor / outlines)", "alto sul fallback: da 47 verso 52-55/55"],
                ["<b>Contratto pulito</b>: Set / Answer / Choose / Abort con l'intento come slot; strumenti filtrati per atto aperto", "semantica incoerente degli strumenti attuali; lo spazio di uscita per stato diventa minimo", "basso (già fatto una volta: cloud 20/20)", "medio: robustezza e generalizzazione a nuovi domini senza toccare ε"],
                ["<b>Frame a due metà</b>: sopra l'atto (ASK: DAY, SAY: BOOKED), sotto lo stato", "l'omni che davanti a MISSING dice \"I'll check\" invece di chiedere; reazioni non uniformi", "basso (tabella stato → atto)", "medio; da misurare a variabile singola"],
                ["<b>Imbuto con conteggi</b>: δ interroga il DB prima di chiedere (\"12 giorni liberi ad aprile, manca il giorno\"; 2-3 opzioni → OFFER)", "l'operatore che chiede a vuoto; il \"prossimo libero\"", "medio (ricerche nel DB, già scritte una volta)", "medio, di prodotto"],
                ["<b>VAD meno aggressivo</b> (600 → 800-900 ms)", "frasi spezzate", "nullo", "piccolo, subito"]], [5.0, 4.6, 3.3, 3.9]))
E.append(Spacer(1, 6))
E += [Paragraph("5.2 Toccando l'omni", H2),
      Paragraph("<b>L'omni che emette gli eventi da solo.</b> Nel suo flusso di testo, token non parlati del tipo ⟨set day=20⟩, ⟨answer yes⟩, ⟨abort⟩, ignorati dal decoder "
                "vocale, letti dalla macchina δ. Sparirebbero il VAD, l'ASR, l'estrattore, la corsa tra frame e risposta, le frasi spezzate, le anafore: l'evento "
                "nascerebbe dallo stesso contesto che ha sentito tutto, con la latenza di un token. L'architettura lo consente: i token di controllo non parlati "
                "esistono già (listen/speak, fine chunk, fine turno) e la separazione testo → voce passa da un decoder vocale separato.", P),
      Paragraph("<b>Cosa serve.</b> Dati: unità omni-flow con l'annotazione degli eventi al posto giusto nel flusso (poche centinaia di dialoghi di sportello bastano per "
                "il formato; la generalità viene dal modello). Training: stadio-ruolo sulla LoRA del backbone, come per l'italiano, con il blocco visivo presente "
                "(il frame resta l'ingresso). Gate: la stessa regressione di oggi, letta dal flusso di testo invece che dall'estrattore, più il test dal vivo.", P),
      Paragraph("<b>Rischi.</b> Il testo dell'omni è legato al parlato: va insegnato che i token evento non si dicono; il rischio è che li pronunci o che li ometta. "
                "Il turn-taking può risentirne (ogni token in più nel turno ritarda il parlato di ~0,1 s). Le sessioni lunghe restano da verificare (finestra KV). "
                "È una scommessa di ricerca, ma è l'unica che rimuove il secondo orecchio invece di renderlo più veloce.", P),
      Paragraph("<b>Cosa sopravvive al salto.</b> Tutto il lato macchina e HUD: R, δ, ρ, il linguaggio del frame, le regressioni. Cambia solo chi produce E.", P)]

E += [Paragraph("6. Percorso consigliato", H1)]
for b in ["<b>Ora, senza toccare l'omni</b>: ASR in streaming con eventi incrementali (il collo di bottiglia misurato), poi decodifica vincolata per il locale, poi il contratto pulito e il frame a due metà come esperimenti a variabile singola, misurati con le regressioni e le righe STATO delle sessioni.",
          "<b>In parallelo, sui dati</b>: raccogliere i dialoghi di sportello (già registrati in data/sessions) e annotare gli eventi: sono il set di training per l'omni nativo e, intanto, la regressione dal vivo.",
          "<b>Poi, toccando l'omni</b>: stadio-ruolo con i token evento, gate in doppio contesto (training e deploy), giudice il test dal vivo. Se passa, ε diventa interno e il sistema resta identico per il resto.",
          "<b>Cosa non fare</b>: strumenti di fuga per il modello (wait, none quando è attraente), istruzioni discorsive sul frame, un secondo turn-taking sopra quello nativo, valori copiabili nello stato dove non sono azionabili. Tutte cose già misurate."]:
    E.append(Paragraph(b, BUL, bulletText="•"))
E += [PageBreak(), Paragraph("7. Implementato il 05/09 senza toccare l'omni: cosa ha dato", H1),
      Paragraph("Tre interventi della tabella 5.1, ognuno misurato a variabile singola dove possibile. Nessuna modifica al modello vocale, al backend o al training.", P)]
E.append(table([["Intervento", "Come", "Misura", "Esito"],
                ["<b>Decisione anticipata alla pausa</b> (primo passo verso lo streaming)", "alla prima pausa di 300 ms il browser manda l'audio detto finora ad ASR + estrattore; a turno confermato (600 ms) il risultato si applica solo se non hai ripreso a parlare, altrimenti si scarta e si rifà. Nessun evento da frasi a metà.", "attesa: fine frase → frame da ~1,8 s a ~1,2 s (la decisione parte 300 ms dopo la pausa invece che 600 ms + calcolo)", "da confermare dal vivo con le righe STATO ("decisione anticipata: usata / scartata")"],
                ["<b>Decodifica vincolata per il locale</b> (lm-format-enforcer)", "grammatica JSON imposta ai token: solo chiamate valide (book / check / cancel / none, campi stringa o null)", "regressione: <b>44/55</b> contro 47 libera; dialogo 18/24 contro 17/20", "<b>scartata</b> come default: sparisce il formato rotto ma il 1,7B, costretto a riempire il JSON, inventa ("Nine" → September 9; "15" → April 15). Resta attivabile (TA_CONSTRAINED=1)"],
                ["<b>Schermo a due metà</b>: atto sopra (ASK: DAY, ASK: CONFIRM BOOKING, SAY: BOOKED…), stato sotto", "tabella stato → atto nel codice; selettore nel pannello (solo stato / due metà) per il confronto nella stessa sessione; riga di prompt da aggiungere", "da misurare: reazioni ai frame più uniformi? letture letterali ("ask day")?", "esperimento pronto, non ancora giudicato"],
                ["Contratto pulito (Set / Answer / Abort), imbuto con conteggi, VAD 800 ms", "—", "—", "non fatti: il contratto a tre strumenti è una scelta esplicita di oggi (cloud 24/24); imbuto e VAD restano in lista"]], [3.6, 5.6, 3.9, 3.7]))
E += [Spacer(1, 6),
      Paragraph("Lezione della decodifica vincolata: togliere al modello la possibilità di sbagliare il formato non lo rende più preciso; lo obbliga a riempire campi che non ha. "
                "Per un modello piccolo, la libertà di non rispondere (nessuna chiamata) vale più della garanzia sintattica. È coerente con tutto il resto: ogni "
                "\"obbligo\" dato al 1,7B è finito in un'invenzione.", P)]

E += [Paragraph("8. Il percorso che tocca l'omni: piano su un ramo separato (solo scritto, non implementato)", H1),
      Paragraph("Obiettivo: l'omni emette gli eventi E da solo, nel suo flusso di testo, con token non parlati. Tutto il lato macchina e HUD resta identico. "
                "Il lavoro va su un ramo di sviluppo separato, con il modello principale (base e v1.3) intoccato e sempre avviabile.", P),
      Paragraph("8.1 Isolamento", H2)]
for b in ["<b>Ramo git</b> <font face='DVM'>omni-eventi</font> in un <b>worktree</b> separato (<font face='DVM'>../MiniCPM-o-Demo-omni-eventi</font>), come già fatto per il ramo puro: stesso .git, cartella diversa, nessun revert per passare dall'uno all'altro. Le modifiche a MiniCPMO45/ restano in commit separati.",
          "<b>Pesi</b>: nessun file esistente viene toccato. Le nuove LoRA vanno in <font face='DVM'>training/releases/omni_eventi_v0_x/</font>; il launcher del ramo (<font face='DVM'>tools/run_demo_eventi.sh</font>) le carica con <font face='DVM'>--pt-path</font>; <font face='DVM'>run_demo_hud.sh</font> e <font face='DVM'>run_demo_v13.sh</font> continuano a caricare base e v1.3. Regola: mai cancellare una release.",
          "<b>Interruttore nel gateway</b>: la sorgente degli eventi è una scelta (<font face='DVM'>events_from = extractor | omni</font>); con <font face='DVM'>omni</font> l'estrattore e l'ASR laterale non partono. Sulla stessa pagina HUD si confrontano le due sorgenti con le stesse regressioni e le stesse righe STATO.",
          "<b>Una GPU</b>: training, valutazione e demo si escludono; corse lunghe con setsid e monitor, come da CLAUDE.md."]:
    E.append(Paragraph(b, BUL, bulletText="•"))
E += [Paragraph("8.2 Il formato degli eventi nel flusso dell'omni", H2),
      Paragraph("Token speciali aggiunti al tokenizer (già estensibile: ci sono i token di controllo listen/speak, fine chunk, fine turno): "
                "<font face='DVM'>⟨ev⟩ … ⟨/ev⟩</font> con dentro un evento dell'algebra in forma compatta, per esempio "
                "<font face='DVM'>⟨ev⟩set day=20⟨/ev⟩</font>, <font face='DVM'>⟨ev⟩answer yes⟨/ev⟩</font>, <font face='DVM'>⟨ev⟩set intent=book⟨/ev⟩</font>, "
                "<font face='DVM'>⟨ev⟩abort⟨/ev⟩</font>. Posizione: all'inizio del turno di risposta dell'omni, prima del testo parlato, nell'unità in cui decide di parlare "
                "(o in un'unità di ascolto, se vogliamo l'evento anche quando non risponde). Il decoder vocale ignora tutto ciò che sta tra ⟨ev⟩ e ⟨/ev⟩ "
                "(filtro nel taglio dei chunk, dove già si escludono i token di controllo dalla storia della penalità). Il backend intercetta gli eventi dal flusso di testo "
                "e li manda alla stessa <font face='DVM'>/api/hud_fsm/event</font> di oggi.", P),
      Paragraph("8.3 I dati", H2)]
for b in ["<b>Sorgente</b>: le sessioni già registrate (<font face='DVM'>data/sessions/</font>: audio dell'utente per unità, testo dell'omni, frame) più dialoghi di sportello generati: scenari D1-D11 e varianti, in inglese prima (distribuzione nativa del base), poi in italiano.",
          "<b>Annotazione</b>: per ogni turno dell'utente, l'evento E corretto, prodotto dalla stessa FSM di oggi (che è deterministica) a partire dalla trascrizione: il set di regressione diventa il set di training. Le unità omni-flow si costruiscono con la pipeline esistente (<font face='DVM'>training/</font>), con il blocco visivo presente (frame dell'HUD) perché il frame resta l'ingresso.",
          "<b>Volume</b>: qualche centinaio di dialoghi (2-4 mila unità) bastano per il formato; la generalità semantica la porta il modello. Le predizioni vanno scritte prima: precisione degli eventi ≥ quella dell'estrattore cloud sul set (51/55, 24/24), latenza dell'evento = latenza del primo token."]:
    E.append(Paragraph(b, BUL, bulletText="•"))
E += [Paragraph("8.4 Training e gate", H2)]
for b in ["<b>Stadio-ruolo</b> sulla LoRA del backbone (come per l'italiano v1.x), poche centinaia di passi, partendo dal base per l'inglese; i pesi del vocale e dell'encoder non si toccano. Contratto di distribuzione compilato prima della corsa (<font face='DVM'>plan/contratto-distribuzione.md</font>): stesso prompt, stessa voce di riferimento, stessi frame del deploy.",
          "<b>Gate in doppia condizione</b>: (1) replay delle sessioni registrate con il backend del ramo, leggendo gli eventi dal flusso di testo e confrontandoli con le attese delle regressioni; (2) test dal vivo di Alessandro sulla pagina HUD con <font face='DVM'>events_from=omni</font>. Si promuove solo chi passa entrambi.",
          "<b>Rischi da misurare</b>: token evento pronunciati o omessi; turn-taking rallentato dai token in più (~0,1 s ciascuno); sessioni lunghe (finestra KV) con i token evento; regressione della voce inglese/italiana. Se fallisce, il ramo resta un ramo e il principale non se ne accorge.",
          "<b>Cosa non cambia</b>: R, δ, ρ, il linguaggio del frame, db.html, le regressioni, il launcher del ramo principale."]:
    E.append(Paragraph(b, BUL, bulletText="•"))

E += [Spacer(1, 10), Paragraph("Fonti interne: plan/ramo-hud.md (specifica, test dal vivo 1-9, misure), analisi-toolcalling.md (§1-8: errori di copia, prompt, cloud, operazioni, semplificazione), tools/tool_agent_eval*.py (75 casi). "
                                "Esterne: doc Qwen function calling; Rasa LLM command generators; benchmark tool-calling dei modelli piccoli; confronto on-device 2026 (BFCL).", PS)]
doc.build(E)
print("ok", OUT)
