# -*- coding: utf-8 -*-
"""Figure of the ns-3 validation, drawn from ns3/report_mem.json (figures/fig_ns3.pdf and .png).

    python ns3/make_figure.py

(a), (b) change of unnecessary handovers against the strength eta in the six configurations of
each environment; (c) change at eta = 24 dB against the prequential skill of the control runs,
with the skill threshold of the system-level study (results/summary.json).
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "experiments"))
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from plotstyle import W2, INK, MUTE, BLUE, ORANGE, AQUA, VIOLET, RED, style, panel, savefig

with open(os.path.join(HERE, "report_mem.json"), encoding="utf-8") as fh:
    N = json.load(fh)
with open(os.path.join(ROOT, "results", "summary.json"), encoding="utf-8") as fh:
    S = json.load(fh)
ETAS = [0, 6, 12, 24, 36]
CELLS = [(200, 8), (200, 16), (200, 30), (400, 8), (400, 16), (400, 30)]
SCOL = {8: AQUA, 16: BLUE, 30: VIOLET}


def fig_ns3():
    fig, ax = plt.subplots(1, 3, figsize=(W2, 2.3), gridspec_kw=dict(wspace=0.3))
    for a, env, letter, title in ((ax[0], "urban", "a", "street grid with buildings"), (ax[1], "base", "b", "open area")):
        a.axhline(0, color=MUTE, lw=0.6, zorder=1)
        for isd, v in CELLS:
            d = N[env]["eta"]["(%d, %d)" % (isd, v)]
            a.plot(ETAS, [d[str(e)]["uho_pm"]["rel_change_pct"] for e in ETAS], marker="o" if isd == 200 else "s", ms=3, lw=0.9,
                   ls="-" if isd == 200 else "--", mfc=SCOL[v] if isd == 200 else "white", color=SCOL[v], zorder=3)
        d = N[env]["eta"]["all cells"]
        a.plot(ETAS, [d[str(e)]["uho_pm"]["rel_change_pct"] for e in ETAS], color=INK, lw=1.6, marker="D", ms=3, zorder=4)
        a.set_xticks(ETAS); a.set_xlabel(r"strength $\eta$ [dB]"); a.set_ylim(-60, 60); style(a, grid="both"); panel(a, letter, title)
    ax[0].set_ylabel("change of unnecessary handovers [%]")
    hs = [Line2D([], [], color=SCOL[v], lw=1.2, label="%d m/s" % v) for v in (8, 16, 30)]
    hs += [Line2D([], [], color=MUTE, lw=0.9, marker="o", ms=3, label="200 m"),
           Line2D([], [], color=MUTE, lw=0.9, ls="--", marker="s", ms=3, mfc="white", label="400 m"),
           Line2D([], [], color=INK, lw=1.6, marker="D", ms=3, label="pooled")]
    ax[0].legend(handles=hs, loc="upper left", ncol=2, handlelength=2.2, columnspacing=1.0, handletextpad=0.4)
    a = ax[2]
    a.axhline(0, color=MUTE, lw=0.6, zorder=1)
    th = S["predict"]["skill_threshold"]["value"]
    a.axvline(th, color=RED, lw=0.8, ls="--", zorder=2)
    a.text(th + 0.008, 57, "threshold %.2f" % th, color=RED, fontsize=7, va="top")
    for env, col, mk, lab in (("urban", BLUE, "o", "street grid"), ("base", ORANGE, "s", "open area")):
        xs, ys, es = [], [], []
        for isd, v in CELLS:
            u = N[env]["eta"]["(%d, %d)" % (isd, v)]["24"]["uho_pm"]
            ctrl = u["mean"] - u["diff"]
            xs.append(N[env]["repeatability"]["isd%d_v%d" % (isd, v)]["per_run"]["skill"]["mean"])
            ys.append(u["rel_change_pct"]); es.append(100 * u["diff_ci95"] / ctrl)
        a.errorbar(xs, ys, yerr=es, fmt=mk, ms=3.5, color=col, elinewidth=0.6, capsize=1.5, label=lab, zorder=3)
    a.set_xlabel("prequential skill of the control runs"); a.set_ylim(-60, 60); a.set_xlim(-0.04, 0.36)
    a.legend(loc="upper right"); style(a, grid="both"); panel(a, "c", r"$\eta$ = 24 dB")
    savefig(fig, "fig_ns3")


if __name__ == "__main__":
    fig_ns3()
