# -*- coding: utf-8 -*-
"""Figure drawn from the per-attempt files of the ns-3 runs (figures/fig_ns3_logs.pdf and .png).

    python ns3/make_figure_logs.py

One configuration (inter-site distance 200 m, 16 m/s), six seeds joined, control (eta = 0) and memory rule
(eta = 24 dB), both environments; the files are in ns3/attempt_logs/.
(a), (b) risk score of the most frequent place of each 40 m bin in the control runs, minus the mean of the log;
(c) mean score of a place from the even-numbered against the odd-numbered users;
(d), (e) change of the unnecessary handovers of a bin, memory rule against control;
(f) margin logged at the handover attempts of the runs with the memory rule.
The script stops if the files do not reproduce results.csv (unnecessary handovers of every run) or
report_mem.json (intraclass correlation and split-half correlation of the joined seeds). The numbers quoted in
the paper are written to ns3/attempt_logs/figure_numbers.json.
"""
import csv, json, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "experiments"))
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Rectangle, Circle
from plotstyle import INK, MUTE, BLUE, ORANGE, style, panel, savefig

WF = 165 / 25.4                 # figure width [in]
LIGHT = "#bdbdbd"


# ---- raw per-attempt files of the ns-3 runs
RAW_ISD, RAW_V, RAW_SEEDS, RES = 200, 16, (1, 2, 3, 4, 5, 6), 40.0
URB_X, URB_Y, STREET = 433.0, 250.0, 20.0
NMIN_PLACE, NMIN_BIN = 10, 12     # fewest attempts of a place / fewest unnecessary handovers of the control in a bin to be drawn (six runs together)


def ns3_sites(env, isd):
    """Site positions as the scenario program places them (hexagonal plan; street grid: moved to the nearest street)."""
    pts = [(0.0, 0.0)] + [(isd * math.cos(k * math.pi / 3), isd * math.sin(k * math.pi / 3)) for k in range(6)]
    if env == "base":
        return pts
    out = []
    for (x, y) in pts:
        best, q = 1e300, (x, y)
        for k in (-1, 0, 1):
            cx = min(max(x, -URB_X), URB_X); d = math.hypot(x - cx, y - k * URB_Y)
            if d < best:
                best, q = d, (cx, k * URB_Y)
        for k in (-1, 0, 1):
            cy = min(max(y, -URB_Y), URB_Y); d = math.hypot(x - k * URB_X, y - cy)
            if d < best:
                best, q = d, (k * URB_X, cy)
        out.append(q)
    return out


def ns3_job(eta, s, isd=RAW_ISD, v=RAW_V):
    return "mem_mem_e%d_d%d_v%d_s%d" % (eta, isd, v, s)


def ns3_attempts(env, eta, isd=RAW_ISD, v=RAW_V, seeds=RAW_SEEDS):
    """Rows of the per-attempt files of one configuration. z: risk score from the observable label (None if the attempt was
    not finished at the end of the run); un: unnecessary by the evaluation label, inside the measured window."""
    res = {r["job_id"]: r for r in csv.DictReader(open(os.path.join(HERE, "mem_" + env, "results.csv"), newline="", encoding="utf-8"))}
    out = []
    for s in seeds:
        job = ns3_job(eta, s, isd, v); n_un = 0
        with open(os.path.join(HERE, "attempt_logs", "mem_" + env, job + "_att.csv"), newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                o = r["outcome_obs"]
                un = r["in_window"] == "1" and r["outcome_eval"] == "unnecessary"
                n_un += un
                out.append(dict(seed=s, t=float(r["t_cmd"]), ue=int(r["ue"]), x=float(r["x"]), y=float(r["y"]), tgt=int(r["tgt"]), un=un, margin=float(r["margin"]),
                                z=None if o == "" else (1.0 if o in ("unnecessary", "early") else (-1.0 if o == "late" else 0.0))))
        if n_un != int(res[job]["unnecessary"]):
            raise SystemExit("%s: %d unnecessary handovers in the per-attempt file, %s in results.csv" % (job, n_un, res[job]["unnecessary"]))
    return out


def ns3_origin(env, isd=RAW_ISD):
    return -((URB_X if env == "urban" else 1.3 * isd) + 100.0)      # lower-left corner of the bin grid of the rule, as in the program


def _bin(e, org):
    return (int(math.floor((e["x"] - org) / RES)), int(math.floor((e["y"] - org) / RES)))


def icc(z, g):
    """Intraclass correlation of z over the groups g (one-way analysis of variance, unbalanced), as in analyze_mem.py."""
    grp = {}
    for v, k in zip(z, g):
        grp.setdefault(k, []).append(v)
    k, n = len(grp), len(z); grand = sum(z) / n
    ssb = sum(len(v) * (sum(v) / len(v) - grand) ** 2 for v in grp.values())
    ssw = sum(sum((x - sum(v) / len(v)) ** 2 for x in v) for v in grp.values())
    msb, msw = ssb / (k - 1), ssw / (n - k)
    n0 = (n - sum(len(v) ** 2 for v in grp.values()) / n) / (k - 1)
    return (msb - msw) / (msb + (n0 - 1) * msw)


def split_half(ev, org):
    """Mean score per place (bin, target) from the even- and from the odd-numbered users; places with at least three
    attempts in each half (the definition of analyze_mem.py)."""
    a, b = {}, {}
    for e in ev:
        k = _bin(e, org) + (e["tgt"],)
        s = (a if e["ue"] % 2 == 0 else b).setdefault(k, [0, 0.0]); s[0] += 1; s[1] += e["z"]
    keys = [k for k in a if k in b and a[k][0] >= 3 and b[k][0] >= 3]
    xa = np.array([a[k][1] / a[k][0] for k in keys]); xb = np.array([b[k][1] / b[k][0] for k in keys])
    return xa, xb, float(np.corrcoef(xa, xb)[0, 1])


def draw_env(a, env, isd=RAW_ISD):
    if env == "urban":
        for bx in (-1, 0):
            for by in (-1, 0):
                a.add_patch(Rectangle((bx * URB_X + STREET / 2, by * URB_Y + STREET / 2), URB_X - STREET, URB_Y - STREET, fc="#e3e3e3", ec="none", zorder=1))
        a.set_xlim(-URB_X - 22, URB_X + 22); a.set_ylim(-URB_Y - 22, URB_Y + 22)
    else:
        R = 1.3 * isd
        a.add_patch(Circle((0, 0), R, fc="none", ec=LIGHT, lw=0.8, ls=(0, (3, 2)), zorder=1))
        a.set_xlim(-R - 22, R + 22); a.set_ylim(-R - 22, R + 22)
    a.set_aspect("equal"); a.set_xticks([]); a.set_yticks([])
    for s in a.spines.values():
        s.set_visible(False)


def draw_bins(a, vals, org, norm):
    cm = plt.get_cmap("RdBu_r")
    for (ix, iy), v in vals.items():
        a.add_patch(Rectangle((org + ix * RES, org + iy * RES), RES, RES, fc=cm(norm(v)), ec="white", lw=0.25, zorder=3))


def draw_sites(a, env, isd=RAW_ISD):
    p = np.array(ns3_sites(env, isd))
    a.plot(p[:, 0], p[:, 1], "^", ms=4.4, mfc="white", mec=INK, mew=0.8, zorder=6)


def fig_ns3_logs():
    """Place-wise view of the raw per-attempt files of the ns-3 runs of one configuration (six seeds joined)."""
    N = json.load(open(os.path.join(HERE, "report_mem.json")))
    key = "isd%d_v%d" % (RAW_ISD, RAW_V)
    fig = plt.figure(figsize=(WF, 3.98), layout="compressed")
    fig.get_layout_engine().set(w_pad=0.02, h_pad=0.03, wspace=0.02, hspace=0.05)
    gs = fig.add_gridspec(2, 3, width_ratios=[(2 * URB_X + 44) / (2 * URB_Y + 44), 1.0, 1.0])
    A = {k: fig.add_subplot(gs[r, c]) for k, (r, c) in dict(a=(0, 0), b=(0, 1), c=(0, 2), d=(1, 0), e=(1, 1), f=(1, 2)).items()}
    n1 = TwoSlopeNorm(0, -0.5, 0.5); n2 = TwoSlopeNorm(0, -60, 60)
    info = {}
    hcol = dict(urban=BLUE, base=ORANGE); hmk = dict(urban="o", base="s"); hlab = dict(urban="street grid", base="open area")
    for env, la, lb in (("urban", "a", "d"), ("base", "b", "e")):
        org = ns3_origin(env)
        ctrl_all = ns3_attempts(env, 0); mem_all = ns3_attempts(env, 24)
        ctrl = [e for e in ctrl_all if e["z"] is not None]
        if any(abs(e["margin"] - 4.0) > 1e-9 for e in ctrl_all):
            raise SystemExit("control run with a margin other than 4 dB")
        want = N[env]["repeatability"][key]["pooled_over_seeds"]
        z = [e["z"] for e in ctrl]; gb = [_bin(e, org) for e in ctrl]; gp = [b + (e["tgt"],) for b, e in zip(gb, ctrl)]
        rho_place, rho_bin = icc(z, gp), icc(z, gb)
        xa, xb, r = split_half(ctrl, org)
        if abs(r - want["half"]) > 1e-6 or len(ctrl) != want["events"] or abs(rho_place - want["rho"]) > 1e-6:
            raise SystemExit("the per-attempt files do not reproduce report_mem.json for %s" % env)
        # (a), (b): risk score of the main place of every bin (the target with the most attempts there), minus the mean of the log
        rbar = sum(z) / len(z)
        cnt, sm = {}, {}
        for g, v in zip(gp, z):
            cnt[g] = cnt.get(g, 0) + 1; sm[g] = sm.get(g, 0.0) + v
        main = {}
        for g, c in cnt.items():
            if g[:2] not in main or c > cnt[main[g[:2]]]:
                main[g[:2]] = g
        risk = {b: sm[g] / cnt[g] - rbar for b, g in main.items() if cnt[g] >= NMIN_PLACE}
        draw_env(A[la], env); draw_bins(A[la], risk, org, n1); draw_sites(A[la], env)
        # (d), (e): change of the unnecessary handovers of a bin, memory rule against control (same seeds, same trajectories)
        u0, u1 = {}, {}
        for d_, src in ((u0, ctrl_all), (u1, mem_all)):
            for e in src:
                if e["un"]:
                    d_[_bin(e, org)] = d_.get(_bin(e, org), 0) + 1
        chg = {b: 100.0 * (u1.get(b, 0) / c - 1.0) for b, c in u0.items() if c >= NMIN_BIN}
        draw_env(A[lb], env); draw_bins(A[lb], chg, org, n2); draw_sites(A[lb], env)
        A["c"].scatter(xa, xb, s=9, marker=hmk[env], color=hcol[env], edgecolor="white", linewidth=0.3, alpha=0.85, zorder=3 if env == "urban" else 4,
                       label="%s, $r$ = %.2f" % (hlab[env], r))
        # (f): logged margin of the memory runs against time, median and central 80 % per minute
        t = np.array([e["t"] for e in mem_all]); m = np.array([e["margin"] for e in mem_all])
        tt = np.arange(0, 900, 60)
        q = np.array([np.percentile(m[(t >= u) & (t < u + 60)], [10, 50, 90]) for u in tt])
        A["f"].fill_between((tt + 30) / 60, q[:, 0], q[:, 2], color=hcol[env], alpha=0.18, lw=0, zorder=2)
        A["f"].plot((tt + 30) / 60, q[:, 1], color=hcol[env], marker=hmk[env], ms=2.6, lw=1.0, zorder=3, label=hlab[env])
        tot0, tot1 = sum(u0.values()), sum(u1.values())
        info[env] = dict(attempts_ctrl=len(ctrl_all), labelled_ctrl=len(ctrl), attempts_mem=len(mem_all), rbar=rbar, half=r, places_half=len(xa),
                         rho_place=rho_place, rho_bin=rho_bin, bins_risk=len(risk), bins_risk_far=sum(1 for v in risk.values() if abs(v) > 0.25), bins_change=len(chg),
                         bins_fewer=sum(1 for v in chg.values() if v < 0), bins_more=sum(1 for v in chg.values() if v > 0),
                         un_ctrl=tot0, un_mem=tot1, un_rel=100.0 * (tot1 / tot0 - 1.0),
                         margin_first_minute=[float(q[0, 0]), float(q[0, 1]), float(q[0, 2])], margin_last_minute=[float(q[-1, 0]), float(q[-1, 1]), float(q[-1, 2])],
                         margin_p10=float(np.percentile(m, 10)), margin_p50=float(np.percentile(m, 50)), margin_p90=float(np.percentile(m, 90)),
                         share_below=float(np.mean(m < 4.0 - 1e-9)), share_above=float(np.mean(m > 4.0 + 1e-9)), share_at_4=float(np.mean(np.abs(m - 4.0) <= 1e-9)))
    panel(A["a"], "a", "street grid, control runs"); panel(A["b"], "b", "open area, control runs")
    panel(A["d"], "d", r"street grid, $\eta$ = 24 dB against control"); panel(A["e"], "e", r"open area, $\eta$ = 24 dB")
    a = A["a"]
    a.text(-URB_X / 2, URB_Y / 2, "building block", fontsize=7, ha="center", va="center", color=MUTE)
    a.plot([URB_X / 2 - 100, URB_X / 2 + 100], [-URB_Y / 2 - 12, -URB_Y / 2 - 12], color=INK, lw=1.4, solid_capstyle="butt", zorder=7)
    a.text(URB_X / 2, -URB_Y / 2, "200 m", fontsize=7, ha="center", va="bottom", color=INK)
    for k_, (norm, lab, ticks) in (("b", (n1, "risk score of the main place\nof the bin, minus mean", [-0.5, -0.25, 0, 0.25, 0.5])), ("e", (n2, "change of unnecessary\nhandovers in the bin [%]", [-60, -30, 0, 30, 60]))):
        cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap="RdBu_r"), ax=A[k_], ticks=ticks, fraction=0.06, pad=0.03, aspect=22)
        cb.ax.tick_params(labelsize=7, length=1.5, pad=1.5); cb.outline.set_linewidth(0.4); cb.set_label(lab, fontsize=7, labelpad=2)
    a = A["c"]
    a.plot([-0.25, 1.05], [-0.25, 1.05], color=MUTE, lw=0.6, zorder=1)
    a.set_xlim(-0.3, 1.08); a.set_ylim(-0.3, 1.08); a.set_xticks([0, 0.5, 1]); a.set_yticks([0, 0.5, 1])
    a.set_xlabel("mean score, even-numbered users"); a.set_ylabel("mean score, odd-numbered")
    a.legend(loc="lower right", handletextpad=0.1, borderaxespad=0.3, frameon=True, framealpha=0.9, edgecolor="none", borderpad=0.2); style(a, grid="both")
    panel(a, "c", "the same place, two halves")
    a = A["f"]
    a.axhline(4.0, color=MUTE, lw=0.6, ls="--", zorder=1)
    a.set_xlim(0, 15); a.set_ylim(0, 9.3); a.set_xticks([0, 5, 10, 15]); a.set_yticks([0, 2, 4, 6, 8])
    a.set_xlabel("time in the run [min]"); a.set_ylabel("margin at the handover [dB]")
    a.legend(loc="upper left", ncol=2, handletextpad=0.3, columnspacing=1.0, borderaxespad=0.2); style(a, grid="both"); panel(a, "f", r"logged margin, $\eta$ = 24 dB")
    savefig(fig, "fig_ns3_logs")
    out = dict(isd=RAW_ISD, speed=RAW_V, seeds=list(RAW_SEEDS), nmin_place=NMIN_PLACE, nmin_bin=NMIN_BIN,
               jobs=[ns3_job(0, RAW_SEEDS[0]), ns3_job(0, RAW_SEEDS[-1]), ns3_job(24, RAW_SEEDS[0]), ns3_job(24, RAW_SEEDS[-1])], **info)
    json.dump(out, open(os.path.join(HERE, "attempt_logs", "figure_numbers.json"), "w"), indent=1)        # numbers quoted in the text and the caption
    print(json.dumps(out))


if __name__ == "__main__":
    fig_ns3_logs()
