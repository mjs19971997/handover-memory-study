# -*- coding: utf-8 -*-
"""Figures of the paper, built from results/summary.json (vector PDF + PNG in figures/).

In all figures a "change" is the relative change of the memory rule against the control
(A3) in per cent; negative means fewer.
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import Normalize, TwoSlopeNorm
from plotstyle import W2, INK, MUTE, BLUE, ORANGE, AQUA, YELLOW, VIOLET, RED, style, panel, savefig
from common import OUT

with open(os.path.join(OUT, "summary.json"), encoding="utf-8") as fh:
    S = json.load(fh)
PROFS = ["pedestrian", "vehicular", "street", "highway", "train"]
PLAB = dict(pedestrian="Pedestrian", vehicular="Open area", street="Street grid", highway="Highway", train="Train")
PCOL = dict(pedestrian=VIOLET, vehicular=YELLOW, street=BLUE, highway=ORANGE, train=AQUA)
PHIS = [1.0, 0.75, 0.5, 0.25, 0.0]
DS = [12.5, 25.0, 50.0, 100.0, 200.0]
rep = lambda v, k: v["rep"][k]["mean"]


def fig_profiles():
    """The five mobility profiles in the reference environment: unnecessary handovers,
    mobility failures, and the repeatability indices of the control runs."""
    fig, ax = plt.subplots(1, 3, figsize=(W2, 2.2), gridspec_kw=dict(wspace=0.38))
    x = np.arange(5)
    for a, key, lab in ((ax[0], "UHO_pm", "unnecessary handovers per user-minute"),
                        (ax[1], "fail_pm", "mobility failures per user-minute")):
        c = [S["profiles"][p][key]["ctrl"] for p in PROFS]; m = [S["profiles"][p][key]["mem"] for p in PROFS]
        a.bar(x - 0.19, [v["mean"] for v in c], 0.36, yerr=[v["ci"] for v in c], color=ORANGE, label="A3 (control)",
              error_kw=dict(lw=0.6, capsize=1.5), zorder=3)
        a.bar(x + 0.19, [v["mean"] for v in m], 0.36, yerr=[v["ci"] for v in m], color=BLUE, label="with outcome memory",
              error_kw=dict(lw=0.6, capsize=1.5), zorder=3)
        for i, p in enumerate(PROFS):
            r = S["profiles"][p][key]["rel"]
            top = max(c[i]["mean"] + c[i]["ci"], m[i]["mean"] + m[i]["ci"])
            a.text(i, top * 1.04, "0%" if abs(r) < 0.5 else f"{r:+.0f}%", ha="center", va="bottom", fontsize=7, color=INK)
        a.set_xticks(x); a.set_xticklabels([PLAB[p] for p in PROFS], rotation=25, ha="right"); a.set_ylabel(lab); style(a)
        a.set_ylim(0, a.get_ylim()[1] * 1.45)                # room for the legend above the bars
    ax[0].legend(loc="upper left"); panel(ax[0], "a"); panel(ax[1], "b")
    a = ax[2]
    for k, lab, col, mk in (("rho", r"repeatability $\rho$", MUTE, "s"), ("half", "split-half correlation", AQUA, "^"),
                            ("skill", "prequential skill", BLUE, "o")):
        a.plot(x, [rep(S["profiles"][p], k) for p in PROFS], marker=mk, color=col, label=lab)
    a.set_xticks(x); a.set_xticklabels([PLAB[p] for p in PROFS], rotation=25, ha="right")
    a.set_ylim(0, 1.3); a.set_yticks([0, 0.25, 0.5, 0.75, 1.0]); a.set_ylabel("index (control runs only)")
    a.legend(loc="upper left"); style(a); panel(a, "c")
    savefig(fig, "fig_profiles")


def heat(ax, Z, fmt, cmap, norm, title, letter, ylab=True, div=True):
    """One 5 x 5 map over the propagation settings: rows = shared share, columns = decorrelation
    distance.  div: diverging colour map (dark at both ends) or sequential (dark at the top)."""
    ax.imshow(Z, cmap=cmap, norm=norm, aspect="auto")
    for i in range(5):
        for j in range(5):
            v = Z[i, j]
            txt = fmt % v
            if float(txt) == 0:                              # no sign on a value that rounds to zero
                txt = txt.replace("+", "").replace("-", "")
            dark = abs(norm(v) - 0.5) > 0.32 if div else norm(v) > 0.6
            ax.text(j, i, txt, ha="center", va="center", fontsize=6.8, color="white" if dark else INK)
    ax.set_xticks(range(5)); ax.set_xticklabels(["12.5", "25", "50", "100", "200"]); ax.set_yticks(range(5))
    ax.set_yticklabels(["1", "0.75", "0.5", "0.25", "0"] if ylab else [])
    ax.set_xlabel(r"decorrelation distance $d_{\mathrm{c}}$ [m]")
    if ylab:
        ax.set_ylabel(r"shared share $\varphi$")
    ax.tick_params(length=0); panel(ax, letter, title)
    for s in ax.spines.values():
        s.set_visible(False)


def grid(p, f):
    """Value f(entry) of every propagation setting of profile p as a 5 x 5 array."""
    return np.array([[f(S["sweep"][f"{p}|{phi}|{d}"]) for d in DS] for phi in PHIS])


def fig_sweep():
    """Effect of the memory over the propagation sweep: unnecessary handovers and failures."""
    fig, ax = plt.subplots(1, 4, figsize=(W2, 2.05), gridspec_kw=dict(wspace=0.12))
    n1 = TwoSlopeNorm(0, -70, 70)
    heat(ax[0], grid("street", lambda v: v["UHO_pm"]["rel"]), "%+.0f", "RdBu_r", n1, "street: unnecessary", "a")
    heat(ax[1], grid("highway", lambda v: v["UHO_pm"]["rel"]), "%+.0f", "RdBu_r", n1, "highway: unnecessary", "b", False)
    heat(ax[2], grid("street", lambda v: v["fail_pm"]["rel"]), "%+.0f", "RdBu_r", n1, "street: failures", "c", False)
    heat(ax[3], grid("highway", lambda v: v["fail_pm"]["rel"]), "%+.0f", "RdBu_r", n1, "highway: failures", "d", False)
    savefig(fig, "fig_sweep")


def fig_index():
    """The repeatability indices over the propagation sweep (control runs only)."""
    fig, ax = plt.subplots(1, 4, figsize=(W2, 2.05), gridspec_kw=dict(wspace=0.12))
    heat(ax[0], grid("street", lambda v: rep(v, "rho")), "%.2f", "Greys", Normalize(0.0, 0.9), r"street: $\rho$", "a", div=False)
    heat(ax[1], grid("street", lambda v: rep(v, "n")), "%.1f", "Greys", Normalize(0, 12), "street: events per place", "b", False,
         div=False)
    heat(ax[2], grid("street", lambda v: rep(v, "skill")), "%.2f", "Blues", Normalize(-0.05, 0.5), "street: skill", "c", False,
         div=False)
    heat(ax[3], grid("highway", lambda v: rep(v, "skill")), "%.2f", "Blues", Normalize(-0.05, 0.5), "highway: skill", "d", False,
         div=False)
    savefig(fig, "fig_index")


def fig_predict():
    """Does an index of the control runs predict the effect of the memory?  One point per environment."""
    pts = [("street" if k.startswith("street") else "highway", v) for k, v in S["sweep"].items()] \
        + [(p, S["profiles"][p]) for p in ("pedestrian", "vehicular", "train")]
    fig, ax = plt.subplots(1, 3, figsize=(W2, 2.25), gridspec_kw=dict(wspace=0.32))
    for a, k, lab, letter in ((ax[0], "rho", r"repeatability $\rho$", "a"), (ax[1], "n", "events per place in the log", "b"),
                              (ax[2], "skill", "prequential skill of a table", "c")):
        a.axhline(0, color=MUTE, lw=0.6, zorder=1)
        seen = set()
        for p, v in pts:
            a.scatter(rep(v, k), v["UHO_pm"]["rel"], s=13, color=PCOL[p], edgecolor="white", linewidth=0.3, zorder=3,
                      label=None if p in seen else PLAB[p])
            seen.add(p)
        a.set_xlabel(lab); style(a, grid="both"); panel(a, letter, r"Spearman $r_s$ = %.2f" % S["predict"][k]["spearman_uho"])
        if k == "n":
            a.set_xscale("log")
    ax[0].set_ylabel("change of unnecessary handovers [%]")
    th = S["predict"]["skill_threshold"]["value"]
    ax[2].axvline(th, color=RED, lw=0.8, ls="--", zorder=2)
    ax[2].text(th + 0.008, 44, "threshold %.2f" % th, color=RED, fontsize=7, va="top")
    ax[2].legend(*ax[0].get_legend_handles_labels(), loc="upper right", handletextpad=0.2)
    savefig(fig, "fig_predict")


def fig_curves():
    """Reference environment: length of the warm-up, length of the log, bin size and strength.
    Panel (b): skill solid, rho dotted.  Panels (c), (d): unnecessary handovers solid, failures dashed."""
    fig, ax = plt.subplots(1, 4, figsize=(W2, 2.1), gridspec_kw=dict(wspace=0.42))
    for p, col, mk in (("street", BLUE, "o"), ("highway", ORANGE, "s")):
        w = [0.0, 60.0, 240.0, 960.0]
        ax[0].plot(range(4), [S["warm"][f"{p}|{x}"]["UHO_pm"]["rel"] for x in w], marker=mk, color=col, label=PLAB[p])
        tm = [60.0, 120.0, 240.0, 480.0, 720.0]
        ax[1].plot(tm, [S["time_rep"][f"{p}|{x}"]["skill"]["mean"] for x in tm], marker=mk, color=col)
        ax[1].plot(tm, [S["time_rep"][f"{p}|{x}"]["rho"]["mean"] for x in tm], marker=mk, color=col, ls=":", mfc="white")
        r = ["10.0", "20.0", "40.0", "80.0", "160.0", "route"]
        ax[2].plot(range(6), [S["res"][f"{p}|{x}"]["UHO_pm"]["rel"] for x in r], marker=mk, color=col)
        ax[2].plot(range(6), [S["res"][f"{p}|{x}"]["fail_pm"]["rel"] for x in r], marker=mk, color=col, ls="--", mfc="white")
        e = [2.0, 4.0, 8.0, 12.0, 16.0, 24.0]
        ax[3].plot(e, [S["eta_curve"][f"{p}|{x}"]["UHO_pm"]["rel"] for x in e], marker=mk, color=col)
        ax[3].plot(e, [S["eta_curve"][f"{p}|{x}"]["fail_pm"]["rel"] for x in e], marker=mk, color=col, ls="--", mfc="white")
    ax[0].set_xticks(range(4)); ax[0].set_xticklabels(["0", "60", "240", "960"]); ax[0].set_xlabel("warm-up [s]")
    ax[0].set_ylabel("change of unnecessary HO [%]")
    ax[1].set_xlabel("length of the log [s]"); ax[1].set_ylabel(r"skill (solid), $\rho$ (dotted)"); ax[1].set_ylim(0, 0.5)
    ax[1].set_xticks([60, 240, 480, 720])
    ax[2].set_xticks(range(6)); ax[2].set_xticklabels(["10", "20", "40", "80", "160", "route"], rotation=30)
    ax[2].set_xlabel("bin size [m]"); ax[2].set_ylabel("change [%]")
    ax[3].set_xlabel(r"strength $\eta$ [dB]"); ax[3].set_ylabel("change [%]")
    for a, l in zip(ax, "abcd"):
        style(a, grid="both"); panel(a, l)
    for a in (ax[0], ax[2], ax[3]):
        a.axhline(0, color=MUTE, lw=0.6, zorder=1)
    ax[1].legend(*ax[0].get_legend_handles_labels(), loc=(0.26, 0.37), handlelength=1.4)
    savefig(fig, "fig_curves")


if __name__ == "__main__":
    fig_profiles(); fig_sweep(); fig_index(); fig_predict(); fig_curves()
