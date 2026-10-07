# -*- coding: utf-8 -*-
"""Figure style of the paper: vector output, true print size, serif type that matches the text.

Every figure is drawn at its final width (190 mm full width) so that the type inside it
is 7-8.5 pt in print.  Each figure is saved as PDF (vector, fonts embedded) and 600-dpi PNG.
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

FIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "figures")
os.makedirs(FIG, exist_ok=True)

W1 = 90 / 25.4          # single-column width [in]
W2 = 190 / 25.4         # full width

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "STIXGeneral", "DejaVu Serif"],
    "mathtext.fontset": "stix",
    "font.size": 8.0,
    "axes.labelsize": 8.0,
    "axes.titlesize": 8.5,
    "xtick.labelsize": 7.5,
    "ytick.labelsize": 7.5,
    "legend.fontsize": 7.5,
    "axes.linewidth": 0.6,
    "axes.edgecolor": "#3c3c3c",
    "axes.labelcolor": "#111111",
    "xtick.color": "#3c3c3c", "ytick.color": "#3c3c3c",
    "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5,
    "xtick.minor.size": 1.5, "ytick.minor.size": 1.5,
    "lines.linewidth": 1.2,
    "lines.markersize": 3.6,
    "grid.color": "#d9d9d9", "grid.linewidth": 0.5,
    "legend.frameon": False,
    "figure.dpi": 150,
    "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
    "pdf.fonttype": 42, "ps.fonttype": 42,       # embed TrueType fonts
    "axes.unicode_minus": False,
})

INK = "#111111"
MUTE = "#5a5a5a"
# categorical palette (colour-vision-deficiency checked)
BLUE, ORANGE, AQUA, YELLOW, VIOLET, RED = "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#4a3aa7", "#e34948"


def style(ax, grid="y"):
    """Light grid behind the data, no top/right spine."""
    ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
    if grid:
        ax.grid(axis=grid, zorder=0)
    ax.set_axisbelow(True)


def panel(ax, letter, title=""):
    """Panel label '(a) title' above the top-left corner."""
    ax.set_title(f"({letter}) {title}".rstrip(), loc="left", pad=3)


def savefig(fig, name):
    for ext, kw in (("pdf", {}), ("png", {"dpi": 600})):
        fig.savefig(os.path.join(FIG, f"{name}.{ext}"), facecolor="white", **kw)
    plt.close(fig)
    print("saved", name)
