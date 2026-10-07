# -*- coding: utf-8 -*-
"""Analysis of the study: results/runs.jsonl and the event logs -> results/summary.json.

Two kinds of numbers are computed for every environment:

* the effect of the memory: the memory rule against the control (A3), paired by seed
  because both rules see the same trajectories, services and shadowing: mean and 95 %
  Student-t confidence interval of each rule, relative change of the means, mean
  paired difference, Wilcoxon signed-rank p-value;
* the repeatability of handover outcomes, from the event log of a long control run
  (memstudy/repeatability.py).  No memory rule is involved in these indices.

The last part asks whether the indices predict the effect: one point per environment
(the 25 propagation settings on the street grid and on the highway, and the three other
mobility profiles), rank correlation between each index and the relative change of the
unnecessary handovers.
"""
import collections, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from scipy import stats

from common import OUT
from run_study import (ETAS, PHIS, DCORRS, BOTH, T_RUN, T_WARM, T_LOG, ENV, CONTROL, BUDGET,
                       stage_main, analysis_logs, log_path, a3_rows)
from memstudy.repeatability import load_log, repeatability

PROFS = ("pedestrian", "vehicular", "street", "highway", "train")
KAPPA = 3.0                                  # pseudo-observations of the shrinkage table behind the skill
DEFAULTS = {"key": "bin", "res": 40.0}       # parameters of the memory rule that a row may not list


def ci(v):
    """Half-width of the 95 % Student-t confidence interval of the mean."""
    v = np.asarray(v, float)
    if len(v) < 2:
        return float("nan")
    return float(stats.t.ppf(0.975, len(v) - 1) * v.std(ddof=1) / np.sqrt(len(v)))


def ms(v):
    return dict(mean=float(np.mean(v)), ci=ci(v), n=len(v))


def select(rows, **kw):
    """Rows whose fields equal the given values (a tuple means: any of these), sorted by seed."""
    def ok(r):
        for k, v in kw.items():
            x = r.get(k, DEFAULTS.get(k))
            if isinstance(v, tuple):
                if x not in v:
                    return False
            elif x != v:
                return False
        return True
    return sorted((r for r in rows if ok(r)), key=lambda r: r["seed"])


def compare(ctrl, mem):
    """Control (A3) against the memory rule, paired by seed."""
    c = {r["seed"]: r for r in ctrl}; m = {r["seed"]: r for r in mem}
    seeds = sorted(set(c) & set(m))
    out = dict(n=len(seeds))
    for k in ("UHO_pm", "fail_pm", "satisf", "HO_pm", "UHR"):
        a = np.array([c[s][k] for s in seeds]); b = np.array([m[s][k] for s in seeds])
        out[k] = dict(ctrl=ms(a), mem=ms(b), rel=float(100 * (b.mean() / a.mean() - 1)), diff=ms(b - a),
                      rel_seed=[float(100 * (y / x - 1)) for x, y in zip(a, b)],
                      same_sign=int(max((b < a).sum(), (b > a).sum())),
                      p=float(stats.wilcoxon(b, a).pvalue) if len(seeds) >= 5 and np.any(b != a) else None)
    return out


def rep_mean(block, profile, phi, d, seeds, **kw):
    """Repeatability indices of the long control runs of one environment, averaged over seeds."""
    out = collections.defaultdict(list)
    for s in seeds:
        path = log_path(f"{block}-{ENV}-{profile}-phi{phi}-d{d}-s{s}-T{int(T_LOG)}-w0-A3")
        for k, v in repeatability(*load_log(path), kappa=KAPPA, **kw).items():
            out[k].append(v)
    return {k: ms(v) for k, v in out.items()}


def check_logs(eta):
    """Stop with an explanation if event logs are missing."""
    need = analysis_logs(stage_main(eta))
    missing = [j["id"] for j in need if not os.path.exists(log_path(j["id"]))]
    if missing:
        raise SystemExit(
            f"{len(missing)} of the {len(need)} event logs that the analysis reads are missing in "
            f"{os.path.join(OUT, 'logs')}\n(first one: {missing[0]}.npz).\n"
            "The event logs are not stored in the repository because of their size.  Re-create them with\n"
            "    python experiments/run_study.py logs\n"
            "which repeats the long control runs (deterministic; about an hour on 6 cores for all of them)\n"
            "and checks each against its row in runs.jsonl.  Then run the analysis again.")


def main():
    path = os.path.join(OUT, "runs.jsonl")
    if not os.path.exists(path) or not os.path.exists(os.path.join(OUT, "tuned_eta.json")):
        raise SystemExit(f"runs.jsonl or tuned_eta.json not found in {OUT}: run 'python experiments/run_study.py' first.")
    with open(path, encoding="utf-8") as fh:
        R = [json.loads(line) for line in fh]
    with open(os.path.join(OUT, "tuned_eta.json"), encoding="utf-8") as fh:
        tuned = json.load(fh)
    ETA = tuned["eta"]
    check_logs(ETA)
    sel = lambda **kw: select(R, **kw)

    S = dict(eta=ETA, kappa=KAPPA, tune=tuned)
    t = sel(block="tune")
    a3 = lambda setting, k: float(np.mean([r[k] for r in a3_rows(t, setting)]))
    S["tune"]["control"] = [a3(CONTROL, k) for k in ("UHO_pm", "fail_pm")]
    S["tune"]["budget_rule"] = [a3(BUDGET, k) for k in ("UHO_pm", "fail_pm")]
    S["tune"]["satisf"] = {str(e): float(np.mean([r["satisf"] for r in t if r["kind"] == "Mem" and r["eta"] == e]))
                           for e in ETAS}

    # ---- the five mobility profiles in the reference environment
    S["profiles"] = {}
    for p in PROFS:
        b = "ref" if p in BOTH else "prof"
        c = compare(sel(block=b, profile=p, kind="A3", T=T_RUN), sel(block=b, profile=p, kind="Mem", warm=T_WARM, eta=ETA))
        c["rep"] = rep_mean(b, p, 1.0, 50.0, range(1, 7))
        S["profiles"][p] = c
        print(p, "UHO %+.0f%%" % c["UHO_pm"]["rel"], "fail %+.0f%%" % c["fail_pm"]["rel"],
              "| rho %.3f n %.1f skill %.3f law %.3f half %.2f"
              % tuple(c["rep"][k]["mean"] for k in ("rho", "n", "skill", "law", "half")), flush=True)

    # ---- propagation sweep: shared share phi x decorrelation distance, three seeds per cell
    S["sweep"] = {}
    for p in BOTH:
        for phi in PHIS:
            for d in DCORRS:
                b = "ref" if (phi == 1.0 and d == 50.0) else "sweep"
                c = compare([r for r in sel(block=b, profile=p, kind="A3", T=T_RUN, phi=phi, d_corr=d) if r["seed"] <= 3],
                            [r for r in sel(block=b, profile=p, kind="Mem", warm=T_WARM, eta=ETA, phi=phi, d_corr=d)
                             if r["seed"] <= 3])
                c["rep"] = rep_mean(b, p, phi, d, range(1, 4))
                S["sweep"][f"{p}|{phi}|{d}"] = c
        print("sweep", p, "done", flush=True)

    # ---- amount of evidence, resolution of the memory, strength (reference environment)
    S["warm"], S["res"], S["eta_curve"], S["res_rep"], S["time_rep"] = {}, {}, {}, {}, {}
    for p in BOTH:
        ctrl = sel(block="ref", profile=p, kind="A3", T=T_RUN)
        for w in (0.0, 60.0, 240.0, 960.0):
            S["warm"][f"{p}|{w}"] = compare(ctrl, sel(block=("warm", "ref"), profile=p, kind="Mem", warm=w, eta=ETA,
                                                      res=40.0, key="bin"))
        for key, res in (("bin", 10.0), ("bin", 20.0), ("bin", 40.0), ("bin", 80.0), ("bin", 160.0), ("route", 40.0)):
            lab = "route" if key == "route" else str(res)
            S["res"][f"{p}|{lab}"] = compare(ctrl, sel(block=("res", "ref"), profile=p, kind="Mem", warm=T_WARM, eta=ETA,
                                                       res=res, key=key))
            S["res_rep"][f"{p}|{lab}"] = rep_mean("ref", p, 1.0, 50.0, range(1, 7), res=res, key=key)
        for e in ETAS:
            S["eta_curve"][f"{p}|{e}"] = compare(ctrl, sel(block=("eta", "ref"), profile=p, kind="Mem", warm=T_WARM, eta=e,
                                                           res=40.0, key="bin"))
        for tm in (60.0, 120.0, 240.0, 480.0, 720.0):
            S["time_rep"][f"{p}|{tm}"] = rep_mean("ref", p, 1.0, 50.0, range(1, 7), t_max=tm)
        print("curves", p, "done", flush=True)

    # ---- do the indices predict the effect?  one point per environment
    pts = list(S["sweep"].items()) + [(p, S["profiles"][p]) for p in ("pedestrian", "vehicular", "train")]
    x = {m: np.array([v["rep"][m]["mean"] for _, v in pts]) for m in ("rho", "skill", "law", "n", "half")}
    y = np.array([v["UHO_pm"]["rel"] for _, v in pts]); yf = np.array([v["fail_pm"]["rel"] for _, v in pts])
    S["predict"] = {m: dict(spearman_uho=float(stats.spearmanr(x[m], y)[0]),
                            spearman_fail=float(stats.spearmanr(x[m], yf)[0]),
                            pearson_uho=float(np.corrcoef(x[m][np.isfinite(x[m])], y[np.isfinite(x[m])])[0, 1]))
                    for m in x}
    S["predict"]["n_points"] = len(pts)
    # threshold on the prequential skill that best separates gain from loss
    order = np.argsort(x["skill"]); best = None
    for i in range(1, len(order)):
        th = 0.5 * (x["skill"][order[i - 1]] + x["skill"][order[i]])
        acc = float(((x["skill"] > th) == (y < 0)).mean())
        if best is None or acc > best[1]:
            best = (float(th), acc)
    S["predict"]["skill_threshold"] = dict(value=best[0], accuracy=best[1])
    S["predict"]["law_vs_skill"] = float(np.corrcoef(x["law"], x["skill"])[0, 1])
    sl = np.polyfit(x["skill"], y, 1); S["predict"]["fit_skill"] = [float(sl[0]), float(sl[1])]

    with open(os.path.join(OUT, "summary.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(S, fh, indent=1)
        fh.write("\n")
    print(json.dumps(S["predict"], indent=1))
    print("wrote", os.path.join(OUT, "summary.json"))


if __name__ == "__main__":
    main()
