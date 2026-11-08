"""Generate colorful IEEE figures for Campus-GPT paper (Fig 1–4)."""
from pathlib import Path
import shutil

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, Rectangle
import matplotlib.patheffects as pe

OUT = Path(__file__).resolve().parent / "figures"
OUT.mkdir(parents=True, exist_ok=True)

# Vibrant palette
C = {
    "blue": "#2563EB",
    "indigo": "#4F46E5",
    "violet": "#7C3AED",
    "pink": "#DB2777",
    "rose": "#E11D48",
    "teal": "#0D9488",
    "cyan": "#0891B2",
    "amber": "#D97706",
    "orange": "#EA580C",
    "green": "#16A34A",
    "lime": "#65A30D",
    "sky": "#0EA5E9",
    "slate": "#334155",
    "light_blue": "#DBEAFE",
    "light_indigo": "#E0E7FF",
    "light_violet": "#EDE9FE",
    "light_pink": "#FCE7F3",
    "light_teal": "#CCFBF1",
    "light_amber": "#FEF3C7",
    "light_green": "#DCFCE7",
    "light_orange": "#FFEDD5",
    "white": "#FFFFFF",
    "bg": "#F8FAFC",
}


def rounded(ax, xy, w, h, text, fc, ec, fontsize=8.5, tw=True, radius=0.08):
    x, y = xy
    p = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.015,rounding_size={radius}",
        linewidth=1.8, edgecolor=ec, facecolor=fc, zorder=3,
    )
    ax.add_patch(p)
    t = ax.text(
        x + w / 2, y + h / 2, text, ha="center", va="center",
        fontsize=fontsize, fontweight="bold" if tw else "normal",
        color="#0F172A", zorder=4, wrap=True,
    )
    return p


def arrow(ax, start, end, color="#475569", lw=2.0, rad=0.0):
    ax.annotate(
        "", xy=end, xytext=start,
        arrowprops=dict(
            arrowstyle="-|>", color=color, lw=lw,
            connectionstyle=f"arc3,rad={rad}",
            mutation_scale=14,
        ),
        zorder=2,
    )


def label(ax, xy, text, color="#64748B", fs=7.5):
    ax.text(xy[0], xy[1], text, ha="center", va="center", fontsize=fs, color=color, style="italic", zorder=5)


def fig1_architecture():
    fig, ax = plt.subplots(figsize=(11, 7.2), dpi=220)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 8)
    ax.axis("off")
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_title(
        "Complete Campus-GPT + UIS Architecture",
        fontsize=14, fontweight="bold", color=C["slate"], pad=10,
    )

    # Layer bands
    ax.add_patch(Rectangle((0.25, 6.35), 11.5, 1.35, facecolor="#EFF6FF", edgecolor="none", zorder=0))
    ax.add_patch(Rectangle((0.25, 4.35), 11.5, 1.7, facecolor="#F5F3FF", edgecolor="none", zorder=0))
    ax.add_patch(Rectangle((0.25, 2.15), 11.5, 1.9, facecolor="#ECFDF5", edgecolor="none", zorder=0))
    ax.add_patch(Rectangle((0.25, 0.25), 11.5, 1.7, facecolor="#FFFBEB", edgecolor="none", zorder=0))

    ax.text(0.4, 7.45, "Presentation", fontsize=8, color=C["blue"], fontweight="bold")
    ax.text(0.4, 5.8, "Application APIs", fontsize=8, color=C["violet"], fontweight="bold")
    ax.text(0.4, 3.8, "Intelligence & Integration", fontsize=8, color=C["teal"], fontweight="bold")
    ax.text(0.4, 1.7, "Data layer (schema-isolated)", fontsize=8, color=C["amber"], fontweight="bold")

    # UI
    rounded(ax, (1.0, 6.55), 4.4, 0.95, "UIS Frontend\nNext.js · :3000", C["light_blue"], C["blue"], 9)
    rounded(ax, (6.6, 6.55), 4.4, 0.95, "Campus-GPT Frontend\nNext.js · :3001", C["light_indigo"], C["indigo"], 9)

    # APIs
    rounded(ax, (1.0, 4.55), 4.4, 1.15, "UIS API (FastAPI) · :8000\nERP SoR · RBAC · Consent · Audit", C["light_violet"], C["violet"], 8.5)
    rounded(ax, (6.6, 4.55), 4.4, 1.15, "Campus-GPT API (FastAPI) · :8002\nChat · RAG · Voice · Admin Eval", C["light_pink"], C["pink"], 8.5)

    # Intelligence row
    rounded(ax, (1.0, 2.4), 2.7, 1.25, "Gemini LLM\n+ Embeddings\n768-D", C["light_orange"], C["orange"], 8)
    rounded(ax, (4.0, 2.4), 2.7, 1.25, "FAISS RAG\ntop-k = 5\nChunk 750", C["light_teal"], C["teal"], 8)
    rounded(ax, (7.0, 2.4), 2.0, 1.25, "Consent\n+ ABAC\ngates", C["light_green"], C["green"], 8)
    rounded(ax, (9.3, 2.4), 1.9, 1.25, "SMTP\nVoice\nCMS", C["light_amber"], C["amber"], 8)

    # Data
    rounded(ax, (1.0, 0.4), 4.4, 1.25, "Postgres schema: uis\nAcademics · Hostel · Fees · Consents", "#FEF9C3", C["amber"], 8.5)
    rounded(ax, (6.6, 0.4), 4.4, 1.25, "Postgres schema: public\nChat · FAISS meta · Eval runs · Analytics", "#FFEDD5", C["orange"], 8.5)

    # Vertical arrows
    for x in (3.2, 8.8):
        arrow(ax, (x, 6.55), (x, 5.75), C["blue"], 2)
        arrow(ax, (x, 4.55), (x, 3.7), C["violet"], 2)
    arrow(ax, (3.2, 2.4), (3.2, 1.7), C["teal"], 2)
    arrow(ax, (8.8, 2.4), (8.8, 1.7), C["pink"], 2)

    # Integration bidirectional
    ax.annotate(
        "", xy=(6.55, 5.15), xytext=(5.45, 5.15),
        arrowprops=dict(arrowstyle="<->", color=C["rose"], lw=2.6, mutation_scale=16),
        zorder=5,
    )
    ax.text(6.0, 5.45, "Integration API\nX-API-Key + JWT", ha="center", fontsize=7.5,
            color=C["rose"], fontweight="bold", zorder=5)

    fig.tight_layout()
    path = OUT / "fig1_architecture.png"
    fig.savefig(path, bbox_inches="tight", facecolor=C["bg"])
    plt.close(fig)
    print("wrote", path)


def fig2_query_workflow():
    fig, ax = plt.subplots(figsize=(11.5, 5.8), dpi=220)
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 6)
    ax.axis("off")
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_title("End-to-End Query Processing Workflow", fontsize=14, fontweight="bold", color=C["slate"], pad=10)

    steps = [
        (0.3, "1. User query\n+ agent desk", C["light_blue"], C["blue"]),
        (2.4, "2. Auth / RBAC\n+ session", C["light_indigo"], C["indigo"]),
        (4.5, "3. Agent scope\n& intent", C["light_violet"], C["violet"]),
        (6.6, "4. UIS gateway\nor FAISS RAG", C["light_teal"], C["teal"]),
        (8.7, "5. Gemini\ngenerate", C["light_orange"], C["orange"]),
        (10.8, "6. Confidence\nθ = 0.7", C["light_pink"], C["pink"]),
    ]
    for x, text, fc, ec in steps:
        rounded(ax, (x, 3.2), 1.9, 1.6, text, fc, ec, 8)

    for i in range(len(steps) - 1):
        x1 = steps[i][0] + 1.9
        x2 = steps[i + 1][0]
        arrow(ax, (x1, 4.0), (x2, 4.0), steps[i][3], 2.2)

    # Branches
    rounded(ax, (5.8, 0.7), 2.8, 1.5, "Structured UIS fact\n→ answer ≈ 0.95\n(consent required)", C["light_green"], C["green"], 8)
    rounded(ax, (9.5, 0.7), 3.0, 1.5, "c < 0.7 → escalate\nlog + department redirect", "#FEE2E2", C["rose"], 8)
    arrow(ax, (7.55, 3.2), (7.2, 2.25), C["green"], 2)
    arrow(ax, (11.7, 3.2), (11.0, 2.25), C["rose"], 2)

    rounded(ax, (0.4, 0.7), 4.4, 1.5, "Also: latency_ms logged · eval harness\nkeyword / token-F1 proxies · analytics", C["light_amber"], C["amber"], 8)

    fig.tight_layout()
    path = OUT / "fig2_query_workflow.png"
    fig.savefig(path, bbox_inches="tight", facecolor=C["bg"])
    plt.close(fig)
    print("wrote", path)


def fig3_rag_uis_flow():
    fig, ax = plt.subplots(figsize=(11, 6.5), dpi=220)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7)
    ax.axis("off")
    fig.patch.set_facecolor(C["bg"])
    ax.set_facecolor(C["bg"])
    ax.set_title("RAG + UIS Personal Data Retrieval Flow", fontsize=14, fontweight="bold", color=C["slate"], pad=10)

    rounded(ax, (4.5, 5.9), 3.0, 0.8, "Incoming query", C["light_blue"], C["blue"], 9)

    # Split
    rounded(ax, (0.6, 3.8), 4.6, 1.5, "Path A — Personal / structured\nConsent check → UIS Integration API\nAttendance · Marks · Fees · Leave", C["light_green"], C["green"], 8.5)
    rounded(ax, (6.8, 3.8), 4.6, 1.5, "Path B — Institutional knowledge\nEmbed (text-embedding-004)\nFAISS top-k=5 → context chunks", C["light_violet"], C["violet"], 8.5)

    arrow(ax, (5.2, 5.9), (2.9, 5.35), C["green"], 2, rad=0.15)
    arrow(ax, (6.8, 5.9), (9.1, 5.35), C["violet"], 2, rad=-0.15)

    rounded(ax, (0.6, 2.0), 4.6, 1.2, "Deny → 403 CONSENT_DENIED\nAllow → factual payload", "#FEF3C7", C["amber"], 8)
    rounded(ax, (6.8, 2.0), 4.6, 1.2, "Sources + relevance scores\n(1/(1+L2 distance))", C["light_teal"], C["teal"], 8)

    arrow(ax, (2.9, 3.8), (2.9, 3.25), C["amber"], 2)
    arrow(ax, (9.1, 3.8), (9.1, 3.25), C["teal"], 2)

    rounded(ax, (3.0, 0.35), 6.0, 1.15, "Gemini generation with agent persona + history\nHeuristic confidence · optional escalation", C["light_orange"], C["orange"], 9)
    arrow(ax, (2.9, 2.0), (5.0, 1.55), C["orange"], 2)
    arrow(ax, (9.1, 2.0), (7.0, 1.55), C["orange"], 2)

    fig.tight_layout()
    path = OUT / "fig3_rag_uis_flow.png"
    fig.savefig(path, bbox_inches="tight", facecolor=C["bg"])
    plt.close(fig)
    print("wrote", path)


def copy_fig4():
    """Copy generated UI mockup into figures/ as fig4."""
    candidates = [
        Path(r"C:\Users\santh\.cursor\projects\c-Users-santh-Campus\assets\fig4_agent_selection_ui.jpg"),
        Path(r"C:\Users\santh\.cursor\projects\c-Users-santh-Campus\assets\fig4_agent_selection_ui.png"),
    ]
    dest = OUT / "fig4_agent_selection_ui.png"
    for src in candidates:
        if src.exists():
            # Keep jpg if png missing — matplotlib/LaTeX can use jpg; also save as .jpg copy
            if src.suffix.lower() == ".jpg":
                dest_jpg = OUT / "fig4_agent_selection_ui.jpg"
                shutil.copy2(src, dest_jpg)
                print("wrote", dest_jpg)
                # Also try convert via PIL if available
                try:
                    from PIL import Image
                    Image.open(src).convert("RGB").save(dest, "PNG")
                    print("wrote", dest)
                except Exception as e:
                    print("png convert skipped:", e)
            else:
                shutil.copy2(src, dest)
                print("wrote", dest)
            return
    print("WARNING: fig4 source image not found; generating placeholder")
    fig, ax = plt.subplots(figsize=(10, 5.6), dpi=220)
    ax.axis("off")
    fig.patch.set_facecolor(C["bg"])
    ax.set_title("Campus-GPT Agent Selection (UI)", fontsize=14, fontweight="bold")
    agents = [
        ("Campus Guide", C["light_blue"], C["blue"]),
        ("Academic", C["light_indigo"], C["indigo"]),
        ("Faculty", C["light_teal"], C["teal"]),
        ("Admission", C["light_orange"], C["orange"]),
        ("Reception", C["light_violet"], C["violet"]),
        ("Hostel", C["light_pink"], C["pink"]),
        ("Warden", "#FFE4E6", C["rose"]),
    ]
    for i, (name, fc, ec) in enumerate(agents):
        x = 0.4 + (i % 4) * 2.4
        y = 3.2 if i < 4 else 1.2
        rounded(ax, (x, y), 2.2, 1.3, name, fc, ec, 9)
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)
    fig.savefig(OUT / "fig4_agent_selection_ui.png", bbox_inches="tight", facecolor=C["bg"])
    plt.close(fig)
    print("wrote placeholder", OUT / "fig4_agent_selection_ui.png")


if __name__ == "__main__":
    fig1_architecture()
    fig2_query_workflow()
    fig3_rag_uis_flow()
    copy_fig4()
    print("done")
