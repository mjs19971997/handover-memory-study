# -*- coding: utf-8 -*-
"""Analysis of the location-memory study: when does a memory of handover outcomes per place help
a plain A3 rule?

    python analyze_mem.py [--smoke]

Input: folders mem_urban and mem_base (results.csv and the per-attempt files res/<job>_att.csv,
res/<job>_rlf.csv). Output: report_mem.txt and report_mem.json. Standard library only.

Part 1 uses only the control runs (eta = 0, i.e. A3 without memory) and asks whether outcomes
are a repeatable property of the place. Every attempt gets a risk score from its
network-observable label: z = +1 unnecessary or too early, 0 useful, -1 too late. A place is a
(40 m location bin, target cell) pair.
    rho    intraclass correlation of z over places (one-way ANOVA, unbalanced design)
    n      attempts per visited place
    skill  prequential skill of a shrinkage table (kappa = 3) that predicts each attempt from the
           earlier attempts of its place: 1 - MSE(table) / MSE(running overall mean); the first
           tenth of the attempts only fills the table
    law    rho * mean of m / (m + k*), k* = (1 - rho) / rho, m = earlier attempts of the place
    half   split-half correlation of the mean z per place between even- and odd-numbered UEs
           (places with at least 3 attempts in each half, at least 10 such places)
Part 2: unnecessary handovers and failures per UE-minute against eta, paired with the control
by seed. Part 3: the same by time window, to show the warm-up of the memory.
"""
import csv
import json
import math
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))

_T975 = [0, 12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179,
         2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086, 2.080, 2.074, 2.069, 2.064, 2.060,
         2.056, 2.052, 2.048, 2.045, 2.042]


def mean_ci(x):
    """Mean and half-width of the 95 % Student-t confidence interval."""
    n = len(x)
    if n == 0:
        return float("nan"), float("nan")
    m = sum(x) / n
    if n < 2:
        return m, float("nan")
    sd = math.sqrt(sum((v - m) ** 2 for v in x) / (n - 1))
    t = _T975[n - 1] if n - 1 <= 30 else 1.96 + 2.4 / (n - 1)
    return m, t * sd / math.sqrt(n)


# Rates per UE-minute are counts divided by the UE-minutes of a run and are stored in results.csv with
# eight significant digits.  Differences of equal counts then differ in the last stored digit, and a
# tolerance of 1e-12 would rank such tied differences as if they were distinct.  For the count rates the
# signed-rank test therefore treats differences within TIE_TOL as tied (and as zero): the rounding error
# of a difference is below 3e-6 for rates up to 30, the smallest true step is 1/UE-minutes >= 0.003.
TIE_TOL = 1e-5


def wilcoxon(d, tol=TIE_TOL):
    """Two-sided exact Wilcoxon signed-rank p-value (average ranks for ties, zeros dropped; differences
    within tol count as tied)."""
    d = [v for v in d if abs(v) > tol]
    n = len(d)
    if n == 0:
        return 1.0, 0
    order = sorted(range(n), key=lambda i: abs(d[i]))
    r2 = [0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and abs(abs(d[order[j + 1]]) - abs(d[order[i]])) <= tol:
            j += 1
        for k in range(i, j + 1):
            r2[order[k]] = (i + 1) + (j + 1)
        i = j + 1
    w = sum(r for r, v in zip(r2, d) if v > 0)
    tot = sum(r2)
    dist = [0.0] * (tot + 1)
    dist[0] = 1.0
    for r in r2:
        for q in range(tot, r - 1, -1):
            dist[q] += dist[q - r]
    zz = float(2 ** n)
    return min(1.0, 2.0 * min(sum(dist[: w + 1]) / zz, sum(dist[w:]) / zz)), n


def fmt(m, ci, p=3):
    if m != m:
        return "n/a"
    if ci != ci:
        return ("%." + str(p) + "f") % m
    return ("%." + str(p) + "f +/- %." + str(p) + "f") % (m, ci)


ROOT = os.path.join(HERE, "smoke") if "--smoke" in sys.argv else HERE
for _i, _a in enumerate(sys.argv):          # --root <dir>: analyse a copy of the stage folders elsewhere
    if _a == "--root" and _i + 1 < len(sys.argv):
        ROOT = os.path.abspath(sys.argv[_i + 1])
FOLDERS = [("urban", "mem_urban"), ("base", "mem_base")]
RES, KAPPA = 40.0, 3.0
RADIO = ("T310_EXPIRY", "HO_COMMAND_LATE", "DURING_HANDOVER", "RLC_MAX_RETX")
OUT = []


def P(s=""):
    OUT.append(s)
    print(s)


def read_csv(p):
    if not os.path.exists(p):
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def zscore(o):
    return 1.0 if o in ("unnecessary", "early") else (-1.0 if o == "late" else 0.0)


def load_events(folder, job, origin=0.0):
    """Attempts of one run with an observable label: (t, ue, place, z, evaluation outcome).
    origin: lower-left corner of the bin grid used by the rule in that run."""
    ev = []
    for r in read_csv(os.path.join(ROOT, folder, "res", job + "_att.csv")):
        if r["outcome_obs"] == "":
            continue                                    # censored by the end of the run
        try:
            x, y = float(r["x"]), float(r["y"])
        except ValueError:
            continue
        b = (int(math.floor((x - origin) / RES)), int(math.floor((y - origin) / RES)), int(r["tgt"]))
        ev.append((float(r["t_cmd"]), int(r["ue"]), b, zscore(r["outcome_obs"]), r["outcome_eval"]))
    ev.sort(key=lambda e: e[0])
    return ev


def icc(z, g):
    groups = defaultdict(list)
    for v, k in zip(z, g):
        groups[k].append(v)
    k, n = len(groups), len(z)
    if k < 2 or n <= k:
        return float("nan")
    grand = sum(z) / n
    ssb = sum(len(v) * (sum(v) / len(v) - grand) ** 2 for v in groups.values())
    ssw = sum(sum((x - sum(v) / len(v)) ** 2 for x in v) for v in groups.values())
    msb, msw = ssb / (k - 1), ssw / (n - k)
    n0 = (n - sum(len(v) ** 2 for v in groups.values()) / n) / (k - 1)
    den = msb + (n0 - 1) * msw
    return (msb - msw) / den if den > 0 else float("nan")


def corr(a, b):
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    sa = math.sqrt(sum((x - ma) ** 2 for x in a)); sb = math.sqrt(sum((x - mb) ** 2 for x in b))
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) if sa > 0 and sb > 0 else float("nan")


def repeatability(ev):
    """Indices of one event list (sorted by time)."""
    if len(ev) < 20:
        return None
    z = [e[3] for e in ev]
    g = [e[2] for e in ev]
    rho = icc(z, g)
    r = max(rho, 1e-6) if rho == rho else 1e-6
    kstar = (1 - r) / r
    cnt, sm = defaultdict(float), defaultdict(float)
    tot = e_tab = e_glb = w = 0.0
    burn = len(z) // 10
    for i in range(len(z)):
        gm = tot / i if i else 0.0
        m = cnt[g[i]]
        pred = (sm[g[i]] + KAPPA * gm) / (m + KAPPA)
        if i >= burn:
            e_tab += (z[i] - pred) ** 2; e_glb += (z[i] - gm) ** 2; w += m / (m + kstar)
        cnt[g[i]] += 1; sm[g[i]] += z[i]; tot += z[i]
    nev = len(z) - burn
    a, b, za, zb = defaultdict(int), defaultdict(int), defaultdict(float), defaultdict(float)
    for e in ev:
        if e[1] % 2 == 0:
            a[e[2]] += 1; za[e[2]] += e[3]
        else:
            b[e[2]] += 1; zb[e[2]] += e[3]
    both = [k for k in cnt if a[k] >= 3 and b[k] >= 3]
    half = corr([za[k] / a[k] for k in both], [zb[k] / b[k] for k in both]) if len(both) >= 10 else float("nan")
    return dict(rho=rho, n=len(z) / len(cnt), places=len(cnt), events=len(z),
                skill=(1 - e_tab / e_glb) if e_glb > 0 else float("nan"),
                law=(max(rho, 0.0) * w / nev) if rho == rho and nev else float("nan"), half=half,
                share_un=sum(1 for v in ev if v[3] > 0) / len(z), share_late=sum(1 for v in ev if v[3] < 0) / len(z))


def mci(v):
    v = [x for x in v if x == x]
    return mean_ci(v)


def part1(rows, folder, js):
    P("  Part 1: repeatability of outcomes by place, control runs (eta = 0)")
    ctrl = [r for r in rows if r["label"] == "mem_e0"]
    P("    %-16s %5s %7s %7s %7s %7s %7s %7s %7s" % ("cell", "runs", "rho", "n/place", "skill", "law", "half", "events", "un share"))
    cells = sorted({(int(float(r["isd"])), int(float(r["speed"]))) for r in ctrl})
    groups = [(c, [r for r in ctrl if (int(float(r["isd"])), int(float(r["speed"]))) == c]) for c in cells]
    for c, rr in groups:
        org = -((433.0 if rr[0].get("scen") == "urban" else 1.3 * c[0]) + 100.0)   # as in the program
        per = [repeatability(load_events(folder, r["job_id"], org)) for r in rr]
        per = [p for p in per if p]
        # pooled over the seeds of the cell (in the urban layout the buildings are the same for every seed)
        pooled_ev = []
        for i, r in enumerate(rr):
            pooled_ev += [(e[0] + 1e6 * i, e[1], e[2], e[3], e[4]) for e in load_events(folder, r["job_id"], org)]
        pooled = repeatability(pooled_ev)
        name = "ISD %d, %d m/s" % c
        if per:
            st = {k: mci([p[k] for p in per]) for k in ("rho", "n", "skill", "law", "half", "events", "share_un")}
            P("    %-16s %5d %7.3f %7.2f %7.3f %7.3f %7.3f %7.0f %7.3f   (mean of the runs)"
              % (name, len(per), st["rho"][0], st["n"][0], st["skill"][0], st["law"][0], st["half"][0],
                 st["events"][0], st["share_un"][0]))
            js.setdefault("repeatability", {})["isd%d_v%d" % c] = dict(
                per_run={k: dict(mean=v[0], ci95=v[1]) for k, v in st.items()}, pooled_over_seeds=pooled)
        if pooled:
            P("    %-16s %5s %7.3f %7.2f %7.3f %7.3f %7.3f %7d %7.3f   (seeds pooled as one log)"
              % ("", "", pooled["rho"], pooled["n"], pooled["skill"], pooled["law"], pooled["half"],
                 pooled["events"], pooled["share_un"]))


def part2(rows, js):
    P("  Part 2: change against the control (eta = 0), paired by seed; rates per UE-minute")
    etas = sorted({int(r["label"].split("_e")[1]) for r in rows})
    cells = sorted({(int(float(r["isd"])), int(float(r["speed"]))) for r in rows})
    val = {(int(r["label"].split("_e")[1]), int(float(r["isd"])), int(float(r["speed"])), int(float(r["rngRun"]))): r
           for r in rows}
    for scope in cells + ["all cells"]:
        cs = cells if scope == "all cells" else [scope]
        P("    %s" % (scope if scope == "all cells" else "ISD %d m, %d m/s" % scope))
        for eta in etas:
            line = "      eta %2d dB:" % eta
            rec = {}
            for m, name in (("uho_pm", "UHO"), ("fail_pm", "failures"), ("ho_pm", "handovers")):
                a, d = [], []
                for (e, isd, v, s), r in val.items():
                    if e == eta and (isd, v) in cs and (0, isd, v, s) in val:
                        x, x0 = float(r[m]), float(val[(0, isd, v, s)][m])
                        a.append(x); d.append(x - x0)
                if not a:
                    continue
                ma = sum(a) / len(a)
                md, ci = mean_ci(d)
                p = wilcoxon(d)[0] if eta else float("nan")
                base = ma - md
                rel = (100 * md / base) if abs(base) > 1e-12 else float("nan")
                rec[m] = dict(mean=ma, diff=md, diff_ci95=ci, rel_change_pct=rel, wilcoxon_p=p, n=len(a))
                rels = ("%+.1f%%" % rel) if rel == rel else "n/a"
                line += "  %s %.3f" % (name, ma) + ("" if not eta else " (%s, diff %s, p=%.2g)" % (rels, fmt(md, ci), p))
            P(line)
            js.setdefault("eta", {}).setdefault(str(scope), {})[str(eta)] = rec


def part3(rows, folder, js):
    P("  Part 3: by time window (attempts by command time, failures by their own time); all cells and seeds")
    windows = None
    acc = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0.0]))     # eta -> window -> [un, fail, UE-min]
    for r in rows:
        eta = int(r["label"].split("_e")[1])
        t_end, t0, n_ue = float(r["simTime"]), float(r["discard"]), float(r["nUe"])
        if windows is None:
            step = (t_end - t0) / 3.0
            windows = [(t0 + i * step, t0 + (i + 1) * step) for i in range(3)]
        for a in read_csv(os.path.join(ROOT, folder, "res", r["job_id"] + "_att.csv")):
            t = float(a["t_cmd"])
            for i, (lo, hi) in enumerate(windows):
                if lo <= t < hi and a["outcome_eval"] == "unnecessary":
                    acc[eta][i][0] += 1
        for a in read_csv(os.path.join(ROOT, folder, "res", r["job_id"] + "_rlf.csv")):
            t = float(a["time_s"])
            for i, (lo, hi) in enumerate(windows):
                if lo <= t < hi and a["cause"] in RADIO:
                    acc[eta][i][1] += 1
        for i, (lo, hi) in enumerate(windows):
            acc[eta][i][2] += n_ue * (hi - lo) / 60.0
    if not windows:
        return
    for i, (lo, hi) in enumerate(windows):
        line = "    %4.0f-%4.0f s:" % (lo, hi)
        for eta in sorted(acc):
            un, fl, um = acc[eta][i]
            u0, f0, um0 = acc[0][i] if 0 in acc else (float("nan"),) * 3
            ru = un / um if um else float("nan")
            rf = fl / um if um else float("nan")
            rel = 100 * (ru / (u0 / um0) - 1) if eta and um0 and u0 else float("nan")
            js.setdefault("windows", {}).setdefault("%d-%d" % (lo, hi), {})[str(eta)] = dict(uho_pm=ru, fail_pm=rf, uho_rel_pct=rel)
            line += "  eta %d: UHO %.3f%s fail %.3f |" % (eta, ru, "" if (not eta or rel != rel) else " (%+.0f%%)" % rel, rf)
        P(line)


def main():
    if not any(os.path.isdir(os.path.join(ROOT, folder, "res")) for _, folder in FOLDERS):
        sys.exit("The per-attempt files (<folder>/res/<job>_att.csv, <job>_rlf.csv) are not here. Parts 1 and 3 need them;\n"
                 "nothing was written, so the existing report_mem.txt / report_mem.json are untouched. See README.md.")
    js = {}
    P("A3 with a location memory of handover outcomes: report")
    P("root: %s" % ROOT)
    for scen, folder in FOLDERS:
        rows = read_csv(os.path.join(ROOT, folder, "results.csv"))
        P()
        if not rows:
            P("%s: no rows yet" % scen)
            continue
        d = js.setdefault(scen, {})
        bad = sum(1 for r in rows if int(float(r["sum_outcomes"])) != int(float(r["attempts"])))
        P("%s scenario: %d runs (%d with outcome counts that do not add up); rule: A3 %s"
          % (scen, len(rows), bad, rows[0]["config"].split("_eta")[0]))
        part1(rows, folder, d)
        part2(rows, d)
        part3(rows, folder, d)
    with open(os.path.join(ROOT, "report_mem.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(OUT) + "\n")
    with open(os.path.join(ROOT, "report_mem.json"), "w", encoding="utf-8") as f:
        json.dump(js, f, indent=1)
    print("written: %s" % os.path.join(ROOT, "report_mem.txt"))


if __name__ == "__main__":
    main()
