import pymupdf, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
S = "/tmp/claude-1000/-home-alex-progetti-MiniCPM-o-Demo/f961457c-85a6-44a5-a2a1-96bdcf75b1aa/scratchpad/pdf"
ROOT = "/home/alex/progetti/MiniCPM-o-Demo"

# --- ritagli delle figure del paper ---
doc = pymupdf.open(f"{ROOT}/docs/minicpm-o-4.5-upstream/MiniCPM-o-4.5-paper.pdf")
crops = {"paper_fig4": (3, (100, 75, 512, 362)), "paper_fig3": (2, (100, 68, 512, 186)), "paper_fig5": (5, (100, 325, 512, 445))}
for name, (pg, rect) in crops.items():
    pix = doc[pg].get_pixmap(dpi=220, clip=pymupdf.Rect(*rect))
    pix.save(f"{S}/{name}.png")

COL = {"stock": "#cfd8dc", "lora": "#ff9800", "infer": "#42a5f5", "reject": "#ef5350", "ctx": "#66bb6a"}

# --- Fig A: mappa dei moduli, originale vs nostro ---
mods = [  # (nome, dimensione, intervento)
    ("Vocoder flow-matching\n(voce -> onda sonora)", "~0.5B", "stock"),
    ("Laringe: speech token decoder\n(testo+hidden -> token vocali)", "0.3B", "reject"),
    ("Cervello: Qwen3-8B\n(capisce, decide, scrive)", "8.19B", "lora"),
    ("Orecchio: Whisper Medium\n+ projector", "0.33B", "stock"),
    ("Occhio: SigLIP + resampler", "0.51B", "stock"),
]
fig, axes = plt.subplots(1, 2, figsize=(11, 6.2))
for ax, title, ours in zip(axes, ["MiniCPM-o 4.5 ORIGINALE", "IL NOSTRO (v1.3 italiano)"], [False, True]):
    ax.set_xlim(0, 10); ax.set_ylim(-1.6, len(mods) + 1.2); ax.axis("off")
    ax.set_title(title, fontsize=14, fontweight="bold", pad=8)
    for i, (name, size, kind) in enumerate(mods):
        c = COL[kind] if ours else COL["stock"]
        hatch = "//" if (ours and kind == "reject") else None
        ax.add_patch(FancyBboxPatch((1, i), 8, 0.8, boxstyle="round,pad=0.05", fc=c, ec="#37474f", lw=1.2, hatch=hatch))
        ax.text(5, i + 0.4, f"{name}   [{size}]", ha="center", va="center", fontsize=9.5)
        if i > 0:
            ax.annotate("", xy=(5, i), xytext=(5, i - 0.2), arrowprops=dict(arrowstyle="->", lw=1.2, color="#37474f"))
    # metronomo (loop 1Hz) a sinistra
    ax.add_patch(FancyBboxPatch((0.05, 0.2), 0.8, len(mods) - 0.4, boxstyle="round,pad=0.03",
                                fc=(COL["infer"] if ours else COL["stock"]), ec="#37474f", lw=1))
    ax.text(0.45, len(mods) / 2, "Metronomo: loop 1Hz\nlisten / speak", rotation=90, ha="center", va="center", fontsize=8)
    # prompt multimodale in basso
    ax.add_patch(FancyBboxPatch((1, -1.3), 8, 0.8, boxstyle="round,pad=0.05",
                                fc=(COL["ctx"] if ours else COL["stock"]), ec="#37474f", lw=1.2))
    ax.text(5, -0.9, "Prompt multimodale:\ntesto di sistema + AUDIO DI RIFERIMENTO (clonaggio voce)"
            if not ours else "Preset italiano:\nprompt in italiano + voce di riferimento italiana + taratura 1.05",
            ha="center", va="center", fontsize=8.5)
    ax.annotate("", xy=(5, -0.5), xytext=(5, -0.1), arrowprops=dict(arrowstyle="<-", lw=1.2, color="#37474f"))
    ax.text(5, len(mods) + 0.6, "audio in ingresso (microfono)  ->  ...  ->  audio in uscita (altoparlante)", ha="center", fontsize=8, style="italic", color="#546e7a")
from matplotlib.patches import Patch
fig.legend(handles=[Patch(fc=COL["stock"], ec="#37474f", label="intatto (stock)"),
                    Patch(fc=COL["lora"], ec="#37474f", label="riaddestrato (LoRA fusa)"),
                    Patch(fc=COL["infer"], ec="#37474f", label="corretto/tarato in inferenza"),
                    Patch(fc=COL["reject"], ec="#37474f", hatch="//", label="tentato e bocciato (pron_03/04)"),
                    Patch(fc=COL["ctx"], ec="#37474f", label="contesto (nessun peso)")],
           loc="lower center", ncol=5, fontsize=9, frameon=False)
plt.tight_layout(rect=(0, 0.06, 1, 1)); plt.savefig(f"{S}/fig_moduli.png", dpi=170); plt.close()

# --- Fig B: dove stanno i parametri e cosa abbiamo toccato ---
names = ["Occhio\n(SigLIP+resampler)", "Orecchio\n(Whisper+proj)", "Cervello\n(Qwen3-8B)", "Laringe\n(speech decoder)"]
vals = [0.507, 0.328, 8.19, 0.316]
kinds = ["stock", "stock", "lora", "reject"]
fig, ax = plt.subplots(figsize=(9, 3.6))
bars = ax.barh(names, vals, color=[COL[k] for k in kinds], edgecolor="#37474f")
for b, v in zip(bars, vals):
    ax.text(v + 0.1, b.get_y() + b.get_height() / 2, f"{v:.2f} B", va="center", fontsize=10)
ax.set_xlabel("miliardi di parametri (totale appreso: 9.34 B)"); ax.set_xlim(0, 9.6)
ax.set_title("Il 88% dei parametri sta nel cervello: e' li' che abbiamo lavorato", fontsize=12)
ax.invert_yaxis(); plt.tight_layout(); plt.savefig(f"{S}/fig_parametri.png", dpi=170); plt.close()

# --- Fig C: i gate misurati v1 -> v1.3 ---
fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
axes[0].bar(["base+demo", "v1", "v1.3"], [0.0, 0.0, 1.06], color=["#b0bec5", COL["lora"], COL["lora"]], edgecolor="#37474f")
axes[0].set_title("Voce per unita' (s)\n1.0 = frase intera, non tronca"); axes[0].set_ylim(0, 1.3)
axes[0].text(2, 1.08, "1.00-1.13", ha="center", fontsize=9); axes[0].text(1, 0.05, "tronca a\nfine turno", ha="center", fontsize=8)
axes[1].bar(["base+demo", "v1", "v1.3"], [55, 70, 100], color=["#b0bec5", COL["lora"], COL["lora"]], edgecolor="#37474f")
axes[1].set_title("Confini di parola corretti (%)\n('chetu' -> 'che tu')"); axes[1].set_ylim(0, 110)
axes[1].text(0, 57, "parole\nincollate", ha="center", fontsize=8); axes[1].text(2, 102, "100%", ha="center", fontsize=9)
axes[2].bar(["base+demo", "v1", "v1.3"], [6, 0, 0], color=["#b0bec5", COL["lora"], COL["lora"]], edgecolor="#37474f")
axes[2].set_title("Auto-dialogo / impersonazione\n(episodi su 9 sonde)"); axes[2].set_ylim(0, 8)
axes[2].text(1, 0.3, "0", ha="center", fontsize=10); axes[2].text(2, 0.3, "0", ha="center", fontsize=10)
for ax in axes: ax.spines[["top", "right"]].set_visible(False)
plt.suptitle("Cancelli comportamentali (2 repliche, contesto di training E di deploy)", fontsize=11)
plt.tight_layout(); plt.savefig(f"{S}/fig_gate.png", dpi=170); plt.close()

# --- Fig D: scala dati per un omni in lingua nuova ---
lab = ["Moshi\n(da zero, EN)", "Raon-Speech\n(EN/KO)", "J-Moshi\n(giapponese)", "Human-1\n(hindi)", "Nostro corpus\n(italiano)", "Nostro dataset\na unita' (v6)"]
hrs = [7_000_000, 1_380_000, 60_000, 26_000, 3_000, 293]
cols = ["#90a4ae", "#90a4ae", "#90a4ae", "#90a4ae", COL["lora"], COL["lora"]]
fig, ax = plt.subplots(figsize=(10, 3.8))
b = ax.bar(lab, hrs, color=cols, edgecolor="#37474f"); ax.set_yscale("log"); ax.set_ylabel("ore di audio (scala log)")
for bb, h in zip(b, hrs):
    ax.text(bb.get_x() + bb.get_width() / 2, h * 1.35, f"{h:,}".replace(",", "."), ha="center", fontsize=9)
ax.set_title("Quante ore servono: la scala reale dei progetti pubblicati vs i nostri dati", fontsize=11)
ax.spines[["top", "right"]].set_visible(False); plt.tight_layout(); plt.savefig(f"{S}/fig_scala.png", dpi=170); plt.close()

# --- Fig E: RAM al boot ---
fig, ax = plt.subplots(figsize=(6.5, 3))
ax.bar(["prima", "dopo i fix"], [30, 3.9], color=["#ef5350", COL["infer"]], edgecolor="#37474f")
ax.axhline(31, ls="--", color="#37474f"); ax.text(1.35, 31.6, "tetto RAM della VM WSL (31 GB)", fontsize=8, ha="right")
ax.set_ylabel("picco RAM al caricamento (GB)"); ax.set_ylim(0, 36)
ax.text(0, 30.8, "30 GB -> crash", ha="center", fontsize=9); ax.text(1, 4.7, "3.9 GB", ha="center", fontsize=9)
ax.set_title("Caricamento pesi: da 4 minuti e crash a 30 secondi", fontsize=11)
ax.spines[["top", "right"]].set_visible(False); plt.tight_layout(); plt.savefig(f"{S}/fig_ram.png", dpi=170); plt.close()
print("figure OK")
