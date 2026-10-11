# -*- coding: utf-8 -*-
"""How well does a threshold on the prequential skill separate gain from loss on environments it was not fitted on?

    python experiments/threshold_eval.py          -> results/threshold_eval.json, results/threshold_eval.txt

Reads the summary of the system-level study and the report of the ns-3 runs; runs no simulation. Standard library only.

One point per environment of the system-level study (the 50 cells of the propagation sweep and the three other
mobility profiles): the prequential skill of the control log and the change of the unnecessary handovers caused by
the memory rule. An environment is a "gain" if the change is negative. A threshold t predicts a gain where skill > t.

Rule for choosing the threshold on a set of calibration environments (the rule of the original analysis): the
candidates are the midpoints between neighbouring skill values of the calibration set, the candidate with the highest
accuracy is taken, and of several with the same accuracy the smallest.

  in-sample              threshold chosen on all environments and scored on the same environments
  leave-one-out          each environment in turn is classified with the threshold chosen on the others
  leave-one-group-out    the same with a whole group held out: a mobility profile, a value of the shared share of the
                         shadowing, or a value of its decorrelation distance (the three other profiles were run in
                         the reference environment, shared share 1 and 50 m, and are held out with those values)
  ns-3                   the 12 configurations of the ns-3 runs classified with the threshold chosen on all
                         environments of the system-level study; nothing of the ns-3 runs enters the threshold
"""
import json, os, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
SUMMARY = os.path.join(HERE, "..", "results", "summary.json")
NS3 = os.path.join(HERE, "..", "ns3", "report_mem.json")
OUT = os.path.join(HERE, "..", "results", "threshold_eval")
ETA_NS3, ALPHA = "24", 0.05


def choose(pts):
    """pts: list of (skill, change). Returns (threshold, accuracy on pts)."""
    xs = sorted(p[0] for p in pts)
    best = None
    for a, b in zip(xs, xs[1:]):
        t = 0.5 * (a + b)
        acc = sum((s > t) == (c < 0) for s, c in pts) / len(pts)
        if best is None or acc > best[1]:
            best = (t, acc)
    return best


def plateau(pts, acc):
    """All thresholds between neighbouring skill values that reach the accuracy acc: (lowest, highest)."""
    xs = sorted(p[0] for p in pts)
    ok = [(a, b) for a, b in zip(xs, xs[1:]) if abs(sum((s > 0.5 * (a + b)) == (c < 0) for s, c in pts) / len(pts) - acc) < 1e-12]
    return min(a for a, _ in ok), max(b for _, b in ok)


def held_out(envs, group_of):
    """envs: list of dicts with name, skill, change. One fold per group."""
    folds, right, total = [], 0, 0
    for g in sorted(set(group_of(e) for e in envs), key=str):
        test = [e for e in envs if group_of(e) == g]; cal = [e for e in envs if group_of(e) != g]
        t, acc_cal = choose([(e["skill"], e["change"]) for e in cal])
        ok = [(e["skill"] > t) == (e["change"] < 0) for e in test]
        folds.append(dict(group=str(g), n_test=len(test), threshold=t, accuracy_calibration=acc_cal, correct=sum(ok),
                          wrong=[e["name"] for e, o in zip(test, ok) if not o]))
        right += sum(ok); total += len(test)
    ts = [f["threshold"] for f in folds]
    return dict(folds=folds, correct=right, n=total, accuracy=right / total,
                threshold_min=min(ts), threshold_median=statistics.median(ts), threshold_max=max(ts))


def main():
    S = json.loads(open(SUMMARY, encoding="utf-8").read().replace("NaN", "null"))
    N = json.loads(open(NS3, encoding="utf-8").read().replace("NaN", "null"))
    envs = []
    for k, v in S["sweep"].items():
        p, phi, d = k.split("|")
        envs.append(dict(name=k, profile=p, phi=float(phi), d=float(d), skill=v["rep"]["skill"]["mean"], change=v["UHO_pm"]["rel"]))
    for p in ("pedestrian", "vehicular", "train"):
        v = S["profiles"][p]
        envs.append(dict(name=p, profile=p, phi=1.0, d=50.0, skill=v["rep"]["skill"]["mean"], change=v["UHO_pm"]["rel"]))
    pts = [(e["skill"], e["change"]) for e in envs]
    t_all, acc_all = choose(pts)
    old = S["predict"]["skill_threshold"]
    if abs(t_all - old["value"]) > 1e-12 or abs(acc_all - old["accuracy"]) > 1e-12 or len(envs) != S["predict"]["n_points"]:
        raise SystemExit("the rule does not reproduce the threshold of summary.json")
    lo, hi = plateau(pts, acc_all)
    gains = sum(c < 0 for _, c in pts)
    R = dict(rule="midpoints between neighbouring skill values of the calibration set; highest accuracy; of equal ones the smallest",
             n_environments=len(envs), gains=gains, losses=len(envs) - gains, accuracy_always_gain=gains / len(envs),
             in_sample=dict(threshold=t_all, correct=round(acc_all * len(envs)), n=len(envs), accuracy=acc_all, same_accuracy_from=lo, same_accuracy_to=hi,
                            wrong=[e["name"] for e in envs if (e["skill"] > t_all) != (e["change"] < 0)]),
             leave_one_out=held_out(envs, lambda e: e["name"]),
             leave_profile_out=held_out(envs, lambda e: e["profile"]),
             leave_shared_share_out=held_out(envs, lambda e: e["phi"]),
             leave_decorrelation_out=held_out(envs, lambda e: e["d"]))
    # the environments that are classified wrongly in at least one held-out evaluation
    by = {e["name"]: e for e in envs}
    wrong = sorted({n for k in ("leave_one_out", "leave_profile_out", "leave_shared_share_out", "leave_decorrelation_out") for f in R[k]["folds"] for n in f["wrong"]},
                   key=lambda n: by[n]["skill"])
    R["held_out_wrong"] = [dict(name=n, profile=by[n]["profile"], skill=by[n]["skill"], change=by[n]["change"]) for n in wrong]
    # ---- ns-3: threshold fixed from the system-level study
    rows = []
    for env in ("urban", "base"):
        for key, rep in N[env]["repeatability"].items():
            isd, v = key.replace("isd", "").split("_v")
            u = N[env]["eta"]["(%s, %s)" % (isd, v)][ETA_NS3]["uho_pm"]
            skill = rep["per_run"]["skill"]["mean"]
            rows.append(dict(environment=env, isd=int(isd), speed=int(v), skill=skill, change=u["rel_change_pct"], p=u["wilcoxon_p"], pairs=u["n"],
                             predicted_gain=skill > t_all, sign_correct=(skill > t_all) == (u["rel_change_pct"] < 0), significant=u["wilcoxon_p"] < ALPHA))
    lose = [r["skill"] for r in rows if r["change"] >= 0]; gain = [r["skill"] for r in rows if r["change"] < 0]
    folds_all = [f["threshold"] for k in ("leave_one_out", "leave_profile_out", "leave_shared_share_out", "leave_decorrelation_out") for f in R[k]["folds"]]
    R["ns3"] = dict(threshold=t_all, eta_dB=int(ETA_NS3), n=len(rows), sign_correct=sum(r["sign_correct"] for r in rows),
                    significant=sum(r["significant"] for r in rows), significant_and_correct=sum(r["significant"] and r["sign_correct"] for r in rows),
                    significant_and_wrong=sum(r["significant"] and not r["sign_correct"] for r in rows),
                    not_significant=[dict(environment=r["environment"], isd=r["isd"], speed=r["speed"], skill=r["skill"], change=r["change"], p=r["p"], sign_correct=r["sign_correct"])
                                     for r in rows if not r["significant"]],
                    all_correct_for_thresholds_from=max(lose) if lose else None, all_correct_for_thresholds_to=min(gain) if gain else None,
                    fold_thresholds_all_correct=sum(1 for t in folds_all if all((r["skill"] > t) == (r["change"] < 0) for r in rows)), fold_thresholds=len(folds_all),
                    configurations=rows)
    with open(OUT + ".json", "w", encoding="utf-8", newline="\n") as fh:
        json.dump(R, fh, indent=1); fh.write("\n")
    L = []
    P = L.append
    P("Skill threshold: in-sample and held-out accuracy (written by %s)" % os.path.basename(__file__))
    P("rule: " + R["rule"])
    P("environments %d: %d with fewer unnecessary handovers (gain), %d with more or the same; always predicting a gain is right in %.1f %%"
      % (len(envs), gains, len(envs) - gains, 100 * gains / len(envs)))
    i = R["in_sample"]
    P("in-sample:               threshold %.4f, %d of %d correct (%.1f %%); the same accuracy for any threshold from %.4f to %.4f" % (i["threshold"], i["correct"], i["n"], 100 * i["accuracy"], lo, hi))
    P("                         wrong: " + ", ".join(i["wrong"]))
    for k, lab in (("leave_one_out", "leave-one-out"), ("leave_profile_out", "leave one profile out"), ("leave_shared_share_out", "leave one shared share out"),
                   ("leave_decorrelation_out", "leave one decorrelation distance out")):
        h = R[k]
        P("%-24s %d of %d correct (%.1f %%); threshold over the %d folds: min %.4f, median %.4f, max %.4f"
          % (lab + ":", h["correct"], h["n"], 100 * h["accuracy"], len(h["folds"]), h["threshold_min"], h["threshold_median"], h["threshold_max"]))
        if k != "leave_one_out":
            for f in h["folds"]:
                P("    held out %-10s %2d environments, threshold %.4f, %2d correct%s" % (f["group"], f["n_test"], f["threshold"], f["correct"], ("; wrong: " + ", ".join(f["wrong"])) if f["wrong"] else ""))
        else:
            P("    wrong: " + ", ".join(n for f in h["folds"] for n in f["wrong"]))
    P("wrong in at least one held-out evaluation: " + "; ".join("%s (skill %.3f, change %+.1f %%)" % (w["name"], w["skill"], w["change"]) for w in R["held_out_wrong"]))
    n3 = R["ns3"]
    P("ns-3 (eta = %d dB), threshold %.4f fixed from the system-level study: sign as predicted in %d of %d configurations" % (n3["eta_dB"], n3["threshold"], n3["sign_correct"], n3["n"]))
    P("    change different from zero (exact Wilcoxon signed-rank test, six pairs, p < %.2f) in %d; of these %d on the predicted side, %d on the other"
      % (ALPHA, n3["significant"], n3["significant_and_correct"], n3["significant_and_wrong"]))
    for r in n3["not_significant"]:
        P("    not different from zero: %s, %d m, %d m/s: skill %.3f, change %+.1f %%, p = %.2f, sign %s" % (r["environment"], r["isd"], r["speed"], r["skill"], r["change"], r["p"], "as predicted" if r["sign_correct"] else "not as predicted"))
    P("    every threshold between %.4f and %.4f gives the sign of all %d; %d of the %d thresholds of the folds above lie in that range"
      % (n3["all_correct_for_thresholds_from"], n3["all_correct_for_thresholds_to"], n3["n"], n3["fold_thresholds_all_correct"], n3["fold_thresholds"]))
    with open(OUT + ".txt", "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
