from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak, KeepTogether
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage
S = "/tmp/claude-1000/-home-alex-progetti-MiniCPM-o-Demo/f961457c-85a6-44a5-a2a1-96bdcf75b1aa/scratchpad/pdf"
OUT = "/home/alex/progetti/MiniCPM-o-Demo/docs/recap-minicpm-o-italiano.pdf"
pdfmetrics.registerFont(TTFont("DV", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("DVB", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("DVI", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf"))
from reportlab.pdfbase.pdfmetrics import registerFontFamily
registerFontFamily("DV", normal="DV", bold="DVB", italic="DVI", boldItalic="DVB")

ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=ss["Heading1"], fontName="DVB", fontSize=17, spaceBefore=10, spaceAfter=8, textColor=colors.HexColor("#1a237e"))
H2 = ParagraphStyle("H2", parent=ss["Heading2"], fontName="DVB", fontSize=12.5, spaceBefore=8, spaceAfter=4, textColor=colors.HexColor("#283593"))
P = ParagraphStyle("P", parent=ss["BodyText"], fontName="DV", fontSize=9.6, leading=13.5, spaceAfter=5)
PS = ParagraphStyle("PS", parent=P, fontSize=8.3, leading=11, textColor=colors.HexColor("#455a64"))
CAP = ParagraphStyle("CAP", parent=P, fontName="DVI", fontSize=8.2, leading=10.5, textColor=colors.HexColor("#546e7a"), spaceAfter=8)
BUL = ParagraphStyle("BUL", parent=P, leftIndent=12, bulletIndent=2)
TITLE = ParagraphStyle("T", parent=ss["Title"], fontName="DVB", fontSize=24, leading=30, textColor=colors.HexColor("#1a237e"))
SUB = ParagraphStyle("SUB", parent=P, fontSize=12, leading=16, textColor=colors.HexColor("#37474f"))

def img(path, width_cm):
    w, h = PILImage.open(path).size
    return Image(path, width=width_cm * cm, height=width_cm * cm * h / w)

def tbl(rows, widths, head=True, fs=8.3):
    data = [[Paragraph(str(c), ParagraphStyle("c", parent=P, fontSize=fs, leading=fs + 2.5, fontName=("DVB" if (head and i == 0) else "DV"))) for c in r] for i, r in enumerate(rows)]
    t = Table(data, colWidths=[w * cm for w in widths], repeatRows=1 if head else 0)
    st = [("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#b0bec5")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
          ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]
    if head: st += [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eaf6"))]
    t.setStyle(TableStyle(st)); return t

def bl(items): return [Paragraph(f"• {x}", BUL) for x in items]

doc = SimpleDocTemplate(OUT, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.6 * cm, bottomMargin=1.6 * cm,
                        title="Come abbiamo insegnato l'italiano a MiniCPM-o 4.5", author="Alessandro")
E = []
# ---------- copertina ----------
E += [Spacer(1, 3 * cm), Paragraph("Come abbiamo insegnato l'italiano a MiniCPM-o 4.5", TITLE), Spacer(1, 0.4 * cm),
      Paragraph("Cosa abbiamo cambiato nella struttura originale, come, e con quali risultati — spiegato in modo semplice, con gli schemi del paper originale a confronto.", SUB),
      Spacer(1, 1 * cm), Paragraph("Progetto: assistente vocale full-duplex in italiano su GPU locale (RTX 5090, 32 GB)", P),
      Paragraph("Autore del lavoro: Alessandro — documento del 2 settembre 2026", P), Spacer(1, 0.6 * cm),
      img(f"{S}/fig_moduli.png", 17.2),
      Paragraph("In un colpo d'occhio: a sinistra il modello originale, a destra il nostro. Arancione = riaddestrato, blu = corretto in inferenza, rosso = tentato e bocciato, verde = contesto senza pesi.", CAP),
      PageBreak()]

# ---------- 1. in due parole ----------
E += [Paragraph("1. In due parole", H1),
      Paragraph("MiniCPM-o 4.5 è un modello «omni» da 9 miliardi di parametri che ascolta, guarda e parla <b>nello stesso momento</b> (full-duplex): ogni secondo decide da solo se stare zitto o parlare. Nasce addestrato solo su cinese e inglese. Noi lo abbiamo portato a conversare in italiano <b>senza cambiare la sua architettura</b>, agendo su quattro leve:", P)]
E += bl(["<b>Il cervello</b> (Qwen3-8B, l'88% dei parametri): riaddestrato con LoRA su un corpus di conversazioni italiane e su dati di identità/ruolo, poi fuso nei pesi. Qui vive tutto il comportamento: capire, rispondere a tono, tenere il ruolo, decidere quando parlare.",
         "<b>Il metronomo</b> (il loop a 1 Hz che governa il tempo): struttura lasciata intatta, ma corretti quattro bug del codice originale che falsavano le decisioni di ascolto e le ripetizioni.",
         "<b>Il contesto</b> (prompt di sistema + audio di riferimento): il timbro «italiano» che si sente viene dal clonaggio vocale sull'audio di riferimento, non da pesi addestrati. Abbiamo costruito il preset italiano di deploy e lo abbiamo reso la fonte di verità della configurazione.",
         "<b>La laringe</b> (il decoder vocale da 0.3B): abbiamo provato a riaddestrarla per la pronuncia; è migliorata ma non abbastanza — è il limite aperto, e sappiamo perché (vedi §7)."])
E += [Paragraph("Occhio, orecchio e vocoder sono rimasti quelli originali: l'orecchio (Whisper) capisce già l'italiano.", P)]

# ---------- 2. il modello originale ----------
E += [Paragraph("2. Il modello originale, spiegato facile", H1),
      Paragraph("<b>Da «a turni» a «full-duplex».</b> I chatbot vocali classici funzionano a turni: prima ascoltano, poi parlano (e mentre parlano sono sordi). MiniCPM-o 4.5 invece percepisce in continuazione anche mentre parla, e può reagire o intervenire da solo (Figura 3 del paper).", P),
      img(f"{S}/paper_fig3.png", 15.5),
      Paragraph("Figura 3 del paper originale: i paradigmi a turni «bloccano» l'ingresso mentre l'AI parla; il full-duplex no.", CAP),
      Paragraph("<b>Com'è fatto dentro (Figura 4 del paper).</b> Immaginalo come un corpo:", P)]
E += bl(["<b>Occhio</b>: SigLIP + resampler (0.51B) — comprime le immagini in 64 token per fotogramma.",
         "<b>Orecchio</b>: Whisper Medium + projector (0.33B) — trasforma l'audio in 10 token al secondo che il cervello capisce. Nota: <i>non produce mai una trascrizione</i>: passa direttamente «feature» continue.",
         "<b>Cervello</b>: Qwen3-8B (8.19B) — capisce tutto e <b>scrive solo testo</b> (3-4 token al secondo, la velocità del parlato umano). Non genera audio: per questo resta intelligente e veloce.",
         "<b>Laringe</b>: decoder vocale da 0.3B — riceve ogni parola del cervello <i>insieme al suo stato nascosto</i> (che porta prosodia e intenzione) e produce 25 «token vocali» al secondo.",
         "<b>Vocoder</b>: un decoder flow-matching trasforma i token vocali in onda sonora, imitando la voce dell'audio di riferimento (clonaggio).",
         "<b>Metronomo</b>: il tempo è diviso in fette da 1 secondo. A ogni fetta il modello ingerisce ciò che vede/sente e sputa PRIMA un token di controllo — <b>listen</b> (sto zitto) o <b>speak</b> (parlo) — e poi, se parla, il testo. Il paper dimostra che 1 secondo è l'ottimo e che separare «se parlare» da «cosa dire» rende l'apprendimento più stabile."])
E += [img(f"{S}/paper_fig4.png", 16.5),
      Paragraph("Figura 4 del paper originale: gli encoder (in basso), il cervello full-duplex (al centro), la laringe e il vocoder (in alto), tutti allineati su una linea del tempo in secondi. A sinistra il prompt multimodale con l'audio di riferimento.", CAP),
      Paragraph("<b>Il trucco del tempo (TAIL, Figura 5).</b> Testo e voce vengono interlacciati in modo che la voce prodotta in ogni secondo duri circa un secondo: così l'audio non «resta indietro» rispetto a ciò che il modello sta pensando ora. È questo vincolo (isocronia: 25 token vocali per secondo di unità) che ha guidato il nostro lavoro sulla densità del testo.", P),
      img(f"{S}/paper_fig5.png", 14.5),
      Paragraph("Figura 5 del paper: (a) testo troppo avanti, (b) rapporto fisso, (c) TAIL: allineato al tempo reale — la strategia di MiniCPM-o 4.5.", CAP),
      Paragraph("<b>Cosa non c'era nel modello originale</b>: nessuna lingua oltre cinese e inglese per la voce (il paper stesso ammette instabilità e mescolanze zh/en), nessuna valutazione dell'interruzione (la parola «barge-in» non compare), e nessuna ricetta ufficiale per riaddestrare la modalità omni/duplex (l'issue #1071 upstream lo conferma: il fine-tuning ufficiale è solo «vision»). Tutto il training che segue lo abbiamo costruito noi dal paper.", P),
      PageBreak()]

# ---------- 3. cosa abbiamo cambiato ----------
E += [Paragraph("3. Cosa abbiamo cambiato, modulo per modulo", H1),
      img(f"{S}/fig_parametri.png", 15),
      Paragraph("Dove stanno i parametri: il cervello domina. Arancione = riaddestrato, rosso = tentato e bocciato, grigio = intatto.", CAP)]
E += [tbl([["Modulo originale", "Dimensione", "Cosa gli abbiamo fatto"],
           ["Occhio (SigLIP + resampler)", "0.51B", "Niente: stock."],
           ["Orecchio (Whisper Medium + projector)", "0.33B", "Niente: stock. Capisce già l'italiano (Whisper è multilingue)."],
           ["Cervello (Qwen3-8B)", "8.19B", "<b>Tutto il training.</b> LoRA in più stadi, poi fusa nei pesi: comportamento in italiano, tenuta del ruolo, zero auto-dialogo, decisioni listen/speak nel contesto italiano, densità del parlato (frasi intere)."],
           ["Metronomo (loop 1 Hz, listen/speak, TAIL)", "meccanismo", "<b>Struttura intatta, taratura corretta</b>: token di ascolto giusto, penalità anti-ripetizione col segno giusto (1.15), taglio del testo a confine di parola, punto operativo length_penalty 1.05."],
           ["Laringe (speech token decoder)", "0.3B", "<b>Tentata</b> (pron_03, pron_04: trainer a turno intero sui due canali del corpus): «più italianizzata ma non sufficiente» all'ascolto. In produzione resta quella stock (sa solo zh/en)."],
           ["Vocoder (flow-matching)", "~0.5B", "Niente: stock."],
           ["Prompt multimodale", "contesto", "<b>Preset italiano</b>: prompt in italiano + voce di riferimento italiana + taratura. Il timbro viene dal clonaggio, non da pesi."]],
          [4.4, 2.6, 10.2])]
E += [Spacer(1, 6), Paragraph("<b>Il dettaglio architetturale che spiega tutto</b>: il cervello passa alla laringe non solo il testo ma anche i suoi <i>stati nascosti</i> (sommati agli embedding del decoder vocale). Per questo riaddestrare il cervello ha migliorato anche ritmo e naturalezza del parlato senza toccare la laringe — ma non poteva correggerne la <i>pronuncia</i>: quella vive nei pesi del decoder da 0.3B, che ha imparato solo cinese e inglese.", P)]

# ---------- 4. le tappe ----------
E += [Paragraph("4. Come lo abbiamo fatto: le tappe", H1),
      tbl([["Tappa", "Cosa", "Perché / esito"],
           ["Diagnosi", "Test dal vivo del modello base con prompt italiano", "Loop, eco della domanda, auto-dialogo, pronuncia cinese-inglese, parole spezzate («fac co»)."],
           ["Struttura prima degli esperimenti", "Lettura del paper: come è stato addestrato su ogni asse; contratto di distribuzione train-vs-deploy", "Ogni corsa parte da una predizione scritta; si elimina ogni differenza tra come alleniamo e come usiamo (prompt, canali, spazi, contesto)."],
           ["Dati", "Corpus italiano (~3.000 ore) copiato in locale; dataset a livello di <b>unità da 1 s</b> (il formato nativo del duplex) con bersagli a parole intere (v6); canali separati per ruolo; convenzione degli spazi ai confini di unità; densità 23→11-14 caratteri/unità", "Il bug del mixdown mono (il modello sentiva la propria voce) e le parole incollate («chetu») nascono qui e qui sono stati risolti."],
           ["Training stadio 1 (corpus)", "LoRA sul cervello, bersagli sul canale utente, 300 passi", "Impara l'italiano parlato e il turn-taking reale."],
           ["Training stadio 2 (ruolo)", "Mix 50/50 identità + corpus, <b>nel contesto del preset di deploy</b>, senza supervisione del fine-turno (a peso pieno causava mutismo)", "<b>v1 comportamentale</b> (it08_b12): accettata dal vivo — ruolo pulito, zero loop, zero auto-dialogo."],
           ["Voce intera", "Bersagli di identità reimpacchettati alla densità del parlato reale", "<b>v1.3</b> (it11_b12): la voce arriva a fine frase; confini di parola 100%; gate passati su 2 repliche."],
           ["Pronuncia", "Trainer a turno intero per la laringe (pron_03/04, 6.000 passi)", "Migliora ma non basta: serve più scala dati (vedi §7)."],
           ["Codice", "Audit del decoder upstream: 4 bug corretti (§5); caricamento pesi a basso consumo RAM", "Loop azzerati (misurato), frammenti eliminati, boot da 4 minuti a 30 secondi."],
           ["Verifica forense", "Registrazioni fedeli di ogni sessione (audio + eventi)", "Hanno permesso di distinguere problemi del modello da problemi del microfono/eco (§6)."]],
          [3.2, 7.0, 7.0])]

# ---------- 5. bug ----------
E += [Paragraph("5. I bug trovati nel codice originale", H1),
      Paragraph("Non solo pesi: leggendo il decoder upstream riga per riga abbiamo trovato errori reali che falsavano il comportamento a prescindere dal training. Il loro effetto è stato verificato con un A/B: togliendoli, loop e frammenti tornano.", P),
      tbl([["Bug", "Effetto", "Fix"],
           ["Il token di «ascolto» puntava al token sbagliato (fine-frase invece di &lt;|listen|&gt;)", "Il meccanismo che favorisce l'ascolto agiva a vuoto: più difficile cedere il turno", "Puntato al token corretto"],
           ["Penalità anti-ripetizione con errore di segno (i token ripetuti con logit negativo venivano <i>favoriti</i>)", "Loop di frasi ripetute («È tutto bene? È tutto bene?»)", "Segno corretto + penalità 1.05→1.15 (misurato: azzera i loop)"],
           ["Temperatura non applicata nel campionamento della chiusura del chunk", "Chiusure premature, tagli a metà parola", "Temperatura applicata come da documentazione"],
           ["Taglio del testo a 28 caratteri secchi, anche a metà parola", "Frammentazione «forn ire», «semplic emente» (fuori distribuzione rispetto al training)", "Taglio a confine di parola con tolleranza; token di controllo esclusi dalla cronologia della penalità"],
           ["Caricamento dei pesi interamente in RAM (fp32 + pt materializzato)", "Picco ~30 GB su VM WSL da 31 GB: crash ripetuti, «disconnessione» di Ubuntu", "mmap + bf16 a flusso: picco 3.9 GB"]],
          [6.2, 5.6, 5.4]),
      Spacer(1, 6), img(f"{S}/fig_ram.png", 11)]

# ---------- 6. risultati ----------
E += [Paragraph("6. I risultati misurati", H1),
      img(f"{S}/fig_gate.png", 16.5),
      Paragraph("Cancelli comportamentali: ogni candidato è valutato nel contesto di training E in quello di deploy (prompt + voce del preset); si promuove solo chi passa entrambi. Giudice finale: il test dal vivo.", CAP)]
E += bl(["<b>v1.3</b>: voce per unità 1.00-1.13 s (frasi intere, prima si troncavano), confini di parola 100% su tutti gli indici di turno, auto-dialogo 0/9, impersonazione reale 0; holdout comportamentale: parla quando deve nell'86% dei casi (speak ratio 0.858), cede il turno nell'89% (TOR 0.891).",
         "<b>Dal vivo</b> (test di Alessandro): turni coerenti, ruolo che tiene, si chiude a fine frase; risposte pertinenti su domande varie. Difetti noti: pronuncia con accento cinese-inglese (laringe), qualche parola incollata ai confini di unità.",
         "<b>Diagnosi forense</b> (2 settembre): un episodio di «regressione» (loop, non si interrompe) è stato ricondotto con misure alle registrazioni di sessione — microfono che mandava zeri digitali a raffiche e voce dell'AI che rientrava dagli altoparlanti (correlazione 0.51-0.59 col mic) — e non al modello: con ingresso pulito il modello ascoltava 48 unità su 51 e rispondeva a tono."])

# ---------- 7. limiti ----------
E += [Paragraph("7. Cosa manca ancora, e perché", H1),
      Paragraph("<b>Pronuncia.</b> Vive nella laringe (0.3B), addestrata solo su cinese/inglese. Il nostro training della laringe (pron_04) l'ha «italianizzata» ma non abbastanza: con ~300 ore di dati a unità stiamo un ordine di grandezza sotto ciò che serve per insegnare una fonetica nuova a un decoder vocale. Alternative come una TTS esterna sono state costruite e scartate per scelta architetturale (cascata).", P),
      Paragraph("<b>Interruzione a metà frase (barge-in).</b> Misurato con un A/B: il modello base originale ignora chi gli parla sopra esattamente come il nostro (22 unità di parlato di fila con la voce dell'utente nel microfono). Non è una nostra regressione: è il limite del platform, e dell'intera categoria — i benchmark 2026 (FLEXI, Full-Duplex-Bench) mostrano che perfino Moshi si ferma solo il 46% delle volte con 2.7 s di ritardo. Il «si interrompe bene» che si ottiene è turn-taking rapido (turni corti, taratura 1.05), non barge-in vero.", P),
      Paragraph("<b>La scala dei dati.</b> La letteratura che ha portato un modello duplex a una lingua nuova (J-Moshi per il giapponese, Human-1 per l'hindi) ha usato decine di migliaia di ore di conversazioni reali per il pre-addestramento e ~1.000 ore curate per la rifinitura; il calcolo è sorprendentemente economico (~100 ore di H100 per Human-1). Il collo di bottiglia sono i dati conversazionali <i>veri</i>: sono quelli che insegnano il turn-taking, mentre i sintetici no.", P),
      img(f"{S}/fig_scala.png", 15.5),
      Paragraph("Ore di audio usate dai progetti pubblicati (grigio) contro i nostri dati (arancione), scala logaritmica.", CAP),
      Paragraph("<b>Prossimo passo naturale</b>: replicare la ricetta Human-1 in italiano (tokenizer italiano, codec congelato, riaddestrare il transformer) espandendo il corpus con audio conversazionale italiano diarizzato — la pipeline dati costruita in questo progetto è esattamente la competenza che serve.", P)]

# ---------- 8. glossario ----------
E += [Paragraph("8. Glossario facile", H1),
      tbl([["Termine", "Significato"],
           ["Full-duplex", "Ascoltare e parlare nello stesso momento, come al telefono. Il contrario è «a turni» (walkie-talkie)."],
           ["End-to-end (e2e)", "Un solo modello dall'audio in ingresso all'audio in uscita, senza trascrizione intermedia. Il contrario è la «cascata»: ASR → LLM → TTS, tre modelli separati."],
           ["ASR / TTS", "Riconoscimento vocale (audio → testo) / sintesi vocale (testo → audio)."],
           ["Unità (chunk)", "La fetta di 1 secondo in cui MiniCPM-o divide il tempo. A ogni unità decide listen o speak."],
           ["Hidden state", "Lo «stato mentale» interno del cervello per ogni parola: un vettore di numeri che porta significato e intenzione. Viene passato alla laringe per dare prosodia."],
           ["LoRA", "Tecnica per riaddestrare un modello grande toccando pochi parametri aggiuntivi, che poi si possono fondere nei pesi originali."],
           ["Token vocale (S3)", "Un «pezzetto di suono» codificato come numero; la laringe ne produce 25 al secondo, il vocoder li trasforma in onda sonora."],
           ["Isocronia", "La regola per cui il testo prodotto in un secondo deve durare circa un secondo di voce (TAIL)."],
           ["Gate (cancello)", "Test automatico con soglia: se il candidato non lo passa, non si promuove."],
           ["Barge-in", "Interrompere qualcuno mentre parla e farlo smettere."]],
          [3.6, 13.6])]

# ---------- 9. fonti ----------
E += [Paragraph("9. Fonti", H1)]
E += [Paragraph(x, PS) for x in [
    "MiniCPM-o 4.5 Technical Report (paper locale in docs/minicpm-o-4.5-upstream/): architettura (Tab. 13), Omni-Flow (§3, Tab. 1), TAIL (§3.4), training (§4-5), limiti (§8).",
    "Repository upstream OpenBMB/MiniCPM-o e issue #1071 (fine-tuning omni non supportato ufficialmente).",
    "Storia tecnica del progetto: calendar.md, plan/audit-20agosto-fable.md, plan/contratto-distribuzione.md, plan/modus-operandi.md; releases in training/releases/ (LEGGIMI.md).",
    "FLEXI (arXiv 2509.22243), Full-Duplex-Bench v1.5 (arXiv 2507.23159), FD-Bench (arXiv 2507.19040): benchmark 2025-26 sul barge-in.",
    "Moshi (arXiv 2410.00037), J-Moshi (arXiv 2506.02979), Human-1 (arXiv 2604.23295), Raon-Speech (arXiv 2605.23912): ricette e scala dati per lingue nuove.",
    "Qwen3-Omni (arXiv 2509.17765) e Qwen3.5-Omni (arXiv 2604.15804): confronto architetturale (Thinker-Talker, a turni, solo API per 3.5)."]]

def footer(canvas, doc):
    canvas.saveState(); canvas.setFont("DV", 7.5); canvas.setFillColor(colors.HexColor("#78909c"))
    canvas.drawString(1.8 * cm, 1.0 * cm, "Come abbiamo insegnato l'italiano a MiniCPM-o 4.5 — Alessandro, 02/09/2026")
    canvas.drawRightString(A4[0] - 1.8 * cm, 1.0 * cm, f"pag. {doc.page}"); canvas.restoreState()

doc.build(E, onFirstPage=footer, onLaterPages=footer)
print("PDF:", OUT)
