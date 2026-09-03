import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from PIL import Image as PILImage
S = "/tmp/claude-1000/-home-alex-progetti-MiniCPM-o-Demo/f961457c-85a6-44a5-a2a1-96bdcf75b1aa/scratchpad/tc"
OUT = "/home/alex/progetti/MiniCPM-o-Demo/docs/schema-tool-calling-hud.pdf"

def box(ax, x, y, w, h, text, fc, fs=9.5, ec="#37474f", bold=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.15", fc=fc, ec=ec, lw=1.3))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, fontweight=("bold" if bold else "normal"), wrap=True)

def arrow(ax, x1, y1, x2, y2, text="", color="#37474f", ls="-", lw=1.4, tx=0, ty=0.15):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="->", mutation_scale=14, color=color, lw=lw, linestyle=ls))
    if text: ax.text((x1 + x2) / 2 + tx, (y1 + y2) / 2 + ty, text, ha="center", va="bottom", fontsize=8, color=color)

# ---------- Figura 1: come avviene ORA ----------
fig, ax = plt.subplots(figsize=(11.5, 6.8)); ax.set_xlim(0, 12); ax.set_ylim(0, 7); ax.axis("off")
box(ax, 0.2, 4.6, 1.8, 1.2, "TU\n(voce al microfono)", "#e3f2fd", bold=True)
box(ax, 3.2, 4.4, 3.2, 1.6, "OMNI  MiniCPM-o 4.5\nsente l'AUDIO GREZZO ogni secondo,\ndecide listen/speak, parla", "#fff3e0", bold=True)
box(ax, 8.2, 4.6, 3.4, 1.2, "TESTO dell'omni\n(già detokenizzato: è gratis)", "#f1f8e9")
arrow(ax, 2.0, 5.2, 3.2, 5.2, "chunk audio 1 s")
arrow(ax, 6.4, 5.2, 8.2, 5.2, "frasi dette")
# percorso laterale
box(ax, 0.2, 1.9, 2.6, 1.3, "ASR Whisper (CPU)\ntrascrive gli ultimi 12 s\ndel tuo microfono (~1 s)", "#ede7f6")
arrow(ax, 1.1, 4.6, 1.1, 3.2, "copia dei chunk", color="#5e35b1", ls="--", tx=0.9)
box(ax, 4.0, 1.7, 3.6, 1.7, "TOOL AGENT  Qwen3-1.7B (GPU, 1-2 s)\nlegge: frasi dell'omni + \"TU: ...\"\ne decide: check_availability(data, ora)", "#fce4ec", bold=True)
arrow(ax, 2.8, 2.55, 4.0, 2.55, "\"TU: is April 2 free?\"", color="#5e35b1")
arrow(ax, 9.9, 4.6, 5.8, 3.4, "TRIGGER: quando una frase\ndell'omni si è assestata (1,2 s)", color="#c62828", tx=1.6, ty=0.05)
box(ax, 8.6, 1.7, 3.0, 1.3, "GESTIONALE (DB)\nslot prenotati", "#e8f5e9")
arrow(ax, 7.6, 2.55, 8.6, 2.55, "verifica")
box(ax, 8.6, 0.1, 3.0, 1.1, "SCHERMO HUD\nCHECKING → BOOKED / AVAILABLE", "#fffde7")
arrow(ax, 10.1, 1.7, 10.1, 1.2, "esito")
arrow(ax, 8.6, 0.65, 4.8, 4.4, "FRAME (solo al cambio)\n→ l'omni lo vede e riprende", color="#2e7d32", ls="--", tx=-1.3, ty=-0.1)
ax.text(6, 6.75, "COME AVVIENE ORA", fontsize=14, fontweight="bold", ha="center")
ax.text(6, 6.35, "linea continua = percorso principale (non tocca l'omni) · tratteggio viola = lavoro laterale · rosso = ciò che fa scattare la decisione", fontsize=8.5, ha="center", color="#546e7a")
plt.tight_layout(); plt.savefig(f"{S}/fig_ora.png", dpi=170); plt.close()

# ---------- Figura 2: cosa consuma cosa ----------
fig, ax = plt.subplots(figsize=(9, 3.6)); ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 4)
box(ax, 0.3, 2.3, 4.2, 1.3, "GPU (32,6 GB)\nomni 23,6 GB + tool agent 3,5 GB\nl'omni deve decodificare 1 unità/s: quando\nQwen genera (1-2 s) la GPU è condivisa → singhiozzo", "#ffebee", fs=8.8)
box(ax, 5.3, 2.3, 4.4, 1.3, "CPU (24 core)\nWhisper small ~1 s per chiamata, pochi core;\nl'omni usa la CPU solo per orchestrare:\ncontesa trascurabile", "#e8f5e9", fs=8.8)
box(ax, 0.3, 0.3, 9.4, 1.5, "MISURATO sulle tue sessioni (registrazioni del gateway):\ncadenza dell'omni 1,00 s per unità (mediana) · chunk del mic ogni 1,00 s · 2-4 singhiozzi di 1,5-1,8 s per sessione,\nnei momenti in cui lavora il tool agent → nessun rallentamento sistematico, qualche mezzo secondo perso ogni tanto", "#eceff1", fs=9)
ax.text(5, 3.85, "COSA STIAMO RALLENTANDO (contesa di risorse, non percorso)", fontsize=12, fontweight="bold", ha="center")
plt.tight_layout(); plt.savefig(f"{S}/fig_risorse.png", dpi=170); plt.close()

# ---------- Figura 3: proposta ----------
fig, ax = plt.subplots(figsize=(11.5, 5.4)); ax.set_xlim(0, 12); ax.set_ylim(0, 5.6); ax.axis("off")
box(ax, 0.2, 3.6, 1.8, 1.2, "TU\n(voce)", "#e3f2fd", bold=True)
box(ax, 3.2, 3.5, 3.2, 1.4, "OMNI\n(invariato: audio grezzo → parla)", "#fff3e0", bold=True)
arrow(ax, 2.0, 4.2, 3.2, 4.2, "chunk 1 s")
box(ax, 0.2, 1.3, 2.6, 1.4, "FINE DEL TUO TURNO\n(energia del mic: parli → taci)\nASR solo della TUA battuta (3-5 s)", "#ede7f6", fs=8.8)
arrow(ax, 1.1, 3.6, 1.1, 2.7, "", color="#5e35b1", ls="--")
box(ax, 4.0, 0.9, 4.0, 2.0, "MACCHINA A STATI (deterministica)\nIDLE → RICHIESTA → CHECKING → ANNUNCIATO\n1) classifica la tua frase (richiesta / conferma / chiacchiera)\n2) solo se richiesta: estrai data/ora — che DEVONO stare\n    nelle TUE parole, mai in quelle dell'operatore\n3) cooldown: stesso slot non riverificato per 60 s", "#fce4ec", fs=8.6, bold=False)
arrow(ax, 2.8, 2.0, 4.0, 2.0, "TRIGGER = il tuo turno", color="#c62828")
arrow(ax, 4.8, 3.5, 5.6, 2.9, "testo omni = solo contesto", color="#546e7a", ls=":", tx=1.5)
box(ax, 8.8, 1.9, 2.9, 1.1, "GESTIONALE → HUD → frame", "#e8f5e9")
arrow(ax, 8.0, 2.0, 8.8, 2.4, "check")
arrow(ax, 9.5, 3.0, 6.0, 3.5, "frame → l'omni riprende", color="#2e7d32", ls="--", tx=0.6, ty=0.1)
ax.text(6, 5.35, "PROPOSTA: decisione al termine del TUO turno, con stato e regole fisse", fontsize=13, fontweight="bold", ha="center")
ax.text(6, 4.95, "meno lavoro laterale (3-5 s trascritti invece di 12, una chiamata per turno tuo) · falsi positivi da frasi dell'operatore: impossibili per costruzione", fontsize=8.5, ha="center", color="#546e7a")
plt.tight_layout(); plt.savefig(f"{S}/fig_proposta.png", dpi=170); plt.close()

# ---------- PDF ----------
pdfmetrics.registerFont(TTFont("DV", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")); pdfmetrics.registerFont(TTFont("DVB", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
registerFontFamily("DV", normal="DV", bold="DVB", italic="DV", boldItalic="DVB")
ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="DVB", fontSize=16, textColor=colors.HexColor("#1a237e"), spaceAfter=6)
P = ParagraphStyle("P", parent=ss["BodyText"], fontName="DV", fontSize=9.8, leading=13.8, spaceAfter=5)
CAP = ParagraphStyle("CAP", parent=P, fontSize=8.3, textColor=colors.HexColor("#546e7a"), spaceAfter=8)
T = ParagraphStyle("T", parent=ss["Title"], fontName="DVB", fontSize=20, leading=26, textColor=colors.HexColor("#1a237e"))
def img(path, w):
    W, H = PILImage.open(path).size; return Image(path, width=w * cm, height=w * cm * H / W)
def bl(items): return [Paragraph("• " + x, ParagraphStyle("b", parent=P, leftIndent=12)) for x in items]
doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.4 * cm, bottomMargin=1.4 * cm, title="Tool calling con l'omni: come avviene e cosa rallenta")
E = [Paragraph("Tool calling con l'omni: come avviene, cosa rallenta, come migliorarlo", T), Spacer(1, 4),
     Paragraph("Ramo HUD — MiniCPM-o 4.5 (omni) + modello separato per il tool calling + schermo dell'operatore. Alessandro, 03/09/2026.", CAP),
     Paragraph("1. Come avviene ora", H1), img(f"{S}/fig_ora.png", 17.5),
     Paragraph("Figura 1. L'omni riceve il tuo audio grezzo e parla; il suo testo è già detokenizzato e non costa nulla. Il tuo testo invece non esiste (end-to-end): lo produce un ASR laterale. Il tool agent legge entrambi e decide la chiamata; il risultato torna all'omni come cambio dello schermo (frame).", CAP)]
E += bl(["<b>Trigger</b>: la decisione parte quando una <b>frase dell'omni</b> si è assestata (1,2 s senza nuovi delta), non sulle tue parole.",
         "<b>Ingresso della decisione</b>: le frasi dell'omni + la trascrizione degli <b>ultimi 12 s del tuo microfono</b> (Whisper su CPU, ~1 s).",
         "<b>Uscita</b>: <i>check_availability(data, ora)</i> → gestionale → schermo HUD → frame all'omni, che lo legge e riprende da solo (misurato: 0,4-0,7 s dopo il frame)."])
E += [Paragraph("2. Cosa stiamo rallentando", H1), img(f"{S}/fig_risorse.png", 15.5),
      Paragraph("Niente sta <b>sul percorso</b> dell'omni: non aspetta la trascrizione né il tool agent. La sola interferenza è la <b>contesa di risorse</b>: il tool agent usa la stessa GPU per 1-2 s a ogni chiamata; Whisper usa un po' di CPU. Effetto misurato: 2-4 singhiozzi di 1,5-1,8 s per sessione, cadenza altrimenti a 1,00 s.", P),
      Paragraph("<b>Togliere l'ASR?</b> Si può, ma allora il tool agent vedrebbe solo le frasi dell'omni, che spesso non ripete data e ora («Let me check.» e basta): è il caso dei 30 secondi di silenzio visti nei test. Il tuo testo serve; va reso più leggero, non eliminato.", P),
      PageBreak(), Paragraph("3. Perché oggi sbaglia (falsi positivi)", H1)]
E += bl(["Vede <b>una frase alla volta</b>, senza sapere chi ha introdotto la data: ha preso per richieste una domanda dell'operatore («…for today or tomorrow evening?») e un annuncio di esito («March 31 at 3 pm is available»).",
         "Non ha memoria delle verifiche già fatte → duplicati; e il buffer di 12 s mescola la tua domanda vecchia con le parole nuove."])
E += [Paragraph("4. Proposta", H1), img(f"{S}/fig_proposta.png", 17.5),
      Paragraph("Figura 2. La decisione parte al termine del tuo turno; una macchina a stati deterministica governa quando consultare il modello; il modello fa due compiti stretti (classificare, poi estrarre) invece di una chiamata aperta; la data deve stare nelle tue parole.", CAP)]
E += bl(["<b>Trigger = il tuo turno</b> (energia del microfono: parli → taci): si trascrive solo la tua battuta (3-5 s) e si decide una volta per turno tuo. Meno lavoro laterale, meno contesa.",
         "<b>Macchina a stati</b>: IDLE → RICHIESTA → CHECKING → ANNUNCIATO; il testo dell'omni entra solo come contesto; cooldown di 60 s sullo stesso slot; nessuna consultazione nel turno subito dopo un frame di esito.",
         "<b>Due passi</b>: classificazione in una parola (richiesta / conferma / chiacchiera / correzione) e, solo se richiesta, estrazione di data e ora con vincolo «devono comparire nelle parole dell'utente».",
         "<b>Contesto vero</b>: ultimi 4-6 turni con ruolo e ordine + stato dello schermo («ultima verifica: March 31 15:00 → BOOKED, 12 s fa») + una <i>reason</i> di una riga nel registro.",
         "<b>Ultima leva</b>, solo se serve: sidecar più grande (Qwen3-4B quantizzato) — costa latenza."])
E += [Paragraph("Predizione: falsi positivi da ~3 per sessione a ~0; latenza della decisione uguale o minore. Il «Let me check» seguito da 30 s di silenzio è invece un comportamento dell'omni e va indagato a parte.", P)]
doc.build(E); print("PDF:", OUT)
