# -*- coding: utf-8 -*-
"""Experiments of the study "When is handover history worth remembering?".

    python experiments/run_study.py            run everything that is not done yet (resumable)
    python experiments/run_study.py smoke      four short runs, to check that the chain works
    python experiments/run_study.py status     what is done and what is missing; runs nothing
    python experiments/run_study.py logs       re-create the event logs that the analysis reads

Every comparison is between two rules on the same trajectories, services and shadowing:

  control      Event A3 with hysteresis 4 dB and time-to-trigger 0.1 s (a setting tuned
               for this layout in preliminary runs)
  memory rule  memstudy.rule.MemA3 with the same hysteresis and time-to-trigger, warmed
               up for 240 s on independent traces of the same environment

Shadowing model: a static field shared by all users (std sigma_s), a private component
correlated along each user's own path (std sigma_p) and a fast temporal component
(1.5 dB, 1 s).  The shared share is phi = sigma_s^2 / (sigma_s^2 + sigma_p^2) with
sigma_s^2 + sigma_p^2 = (4 dB)^2; phi = 1 is the default of the simulator.

Output (directory results/, or the one named by MEMSTUDY_RESULTS):
  runs.jsonl       one JSON line per run: the metrics of the simulator plus the job description
  tuned_eta.json   the selected strength eta of the memory rule and the validation table
  logs/<id>.npz    event log of every logged control run (input of experiments/analyze.py)
"""
import os, sys, json, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from functools import partial
from multiprocessing import Pool

import numpy as np

import common
from common import OUT, shadow, n_procs
from hosim.simulator import simulate
from hosim.policies import A3
from memstudy.rule import MemA3
from memstudy.repeatability import load_log, repeatability

ENV, USERS = "UDN-40", 300
H0, TTT0 = 4.0, 0.1                  # hysteresis [dB] and time-to-trigger [s] of the control and of the memory rule
CONTROL = dict(hyst=H0, ttt=TTT0)
BUDGET = dict(hyst=3.0, ttt=0.3)     # the A3 setting whose failure rate is the budget when eta is selected
ETAS = (2.0, 4.0, 8.0, 12.0, 16.0, 24.0)     # candidate strengths of the memory rule [dB]
T_RUN, T_WARM, T_LOG = 240.0, 240.0, 720.0   # test run, warm-up of the memory rule, long logged control run [s]
BOTH = ("street", "highway")
PHIS = (1.0, 0.75, 0.5, 0.25, 0.0)           # shared share of the shadowing variance
DCORRS = (12.5, 25.0, 50.0, 100.0, 200.0)    # decorrelation distance [m]
COUNTS = ("HO", "unnecessary", "failed")     # integer counts that a repeated run must reproduce


# ----------------------------------------------------------------------------
# one run
# ----------------------------------------------------------------------------
def make_policy(spec):
    """Decision rule from its job description (kind, keyword arguments)."""
    kind, kw = spec
    return A3(**kw) if kind == "A3" else MemA3(**kw)


def log_path(job_id, out=OUT):
    return os.path.join(out, "logs", job_id + ".npz")


def run_job(job, out=OUT):
    """Run one job and return its row: the metrics of the simulator and the job description."""
    t0 = time.time()
    P = common.params(job["T"], **job.get("P", {}))
    env = common.make_env(job["env"], P, job["seed"])
    pol = make_policy(job["pol"])
    warm = job.get("warm", 0.0)
    if warm and job["pol"][0] == "Mem":            # fill the memory on independent traces of the same environment
        ps = 5000 + job["seed"]
        Pw = common.params(warm, **job.get("P", {}))
        tr, sv = common.scenario(env, job["profile"], job["users"], Pw, ps)
        pol.persist = True
        simulate(env, pol, tr, sv, Pw, seed=ps)
    traj, svc = common.scenario(env, job["profile"], job["users"], P, job["seed"])
    log = [] if job.get("log") else None
    r = simulate(env, pol, traj, svc, P, seed=job["seed"], log=log)
    if log is not None:
        os.makedirs(os.path.join(out, "logs"), exist_ok=True)
        np.savez_compressed(log_path(job["id"], out), ev=np.asarray(log, dtype=np.float32),
                            box=np.array([env.xmin, env.xmax, env.ymin, env.ymax]),
                            M=env.M, U=job["users"], T=job["T"])
        r["n_events"] = len(log)
    r = {k: (float(v) if isinstance(v, (np.floating, np.integer)) else v) for k, v in r.items()}
    r.update(id=job["id"], env=job["env"], profile=job["profile"], seed=job["seed"], T=job["T"], warm=warm,
             kind=job["pol"][0], secs=round(time.time() - t0, 1), **job.get("tag", {}))
    return r


# ----------------------------------------------------------------------------
# job list
# ----------------------------------------------------------------------------
A3C = ("A3", dict(CONTROL))                        # the control


def mem(**kw):
    """The memory rule with the hysteresis and time-to-trigger of the control."""
    return ("Mem", dict(CONTROL, **kw))


def J(block, profile, seed, pol, T=T_RUN, warm=0.0, log=False, phi=1.0, d=50.0, **tag):
    """One job.  Its id names everything that distinguishes it from the other jobs; the
    hysteresis and the time-to-trigger appear only where they differ from the control."""
    kw = pol[1]
    shown = [k for k in sorted(kw) if k != "name" and kw[k] != CONTROL.get(k)]
    pid = pol[0] + "".join(f"_{k}{kw[k]}" for k in shown)
    jid = f"{block}-{ENV}-{profile}-phi{phi}-d{d}-s{seed}-T{int(T)}-w{int(warm)}-{pid}"
    return dict(id=jid, env=ENV, profile=profile, users=USERS, seed=seed, T=T, warm=warm, log=log, pol=pol,
                P=shadow(phi, d),
                tag=dict(block=block, phi=phi, d_corr=d, **{k: v for k, v in kw.items() if k != "name"}, **tag))


def triple(block, profile, seed, eta, phi=1.0, d=50.0):
    """Control, memory rule (warmed up on other traces) and, for the offline analysis,
    a long logged control run."""
    return [J(block, profile, seed, A3C, phi=phi, d=d, log=True),
            J(block, profile, seed, mem(eta=eta), warm=T_WARM, phi=phi, d=d),
            J(block, profile, seed, A3C, T=T_LOG, log=True, phi=phi, d=d)]


def stage_tune():
    """Validation runs (seeds 101 and 102, never used for testing): the control, the A3
    setting that defines the failure budget, and the candidate strengths."""
    j = []
    for p in BOTH:
        for s in (101, 102):
            j.append(J("tune", p, s, A3C))
            j.append(J("tune", p, s, ("A3", dict(BUDGET))))
            j += [J("tune", p, s, mem(eta=e), warm=T_WARM) for e in ETAS]
    return j


def stage_main(eta):
    """Test runs with the selected strength eta."""
    j = []
    for p in BOTH:                                        # reference environment (phi = 1, 50 m), six seeds
        for s in range(1, 7):
            j += triple("ref", p, s, eta)
    for p in ("pedestrian", "vehicular", "train"):        # the other mobility profiles
        for s in range(1, 7):
            j += triple("prof", p, s, eta)
    for p in BOTH:                                        # how much evidence: length of the warm-up
        for s in range(1, 7):
            j += [J("warm", p, s, mem(eta=eta), warm=w) for w in (0.0, 60.0, 960.0)]
    for p in BOTH:                                        # resolution of the memory
        for s in range(1, 7):
            j += [J("res", p, s, mem(eta=eta, res=r), warm=T_WARM) for r in (10.0, 20.0, 80.0, 160.0)]
            j.append(J("res", p, s, mem(eta=eta, key="route"), warm=T_WARM))
    for p in BOTH:                                        # strength of the reaction
        for s in range(1, 7):
            j += [J("eta", p, s, mem(eta=e), warm=T_WARM) for e in ETAS if e != eta]
    for phi in PHIS:                                      # the propagation sweep, three seeds per cell
        for d in DCORRS:
            if phi == 1.0 and d == 50.0:
                continue                                  # the reference environment
            for p in BOTH:
                for s in range(1, 4):
                    j += triple("sweep", p, s, eta, phi=phi, d=d)
    return j


# ----------------------------------------------------------------------------
# selection of eta
# ----------------------------------------------------------------------------
def a3_rows(rows, setting):
    """The A3 rows with the given hysteresis and time-to-trigger."""
    return [r for r in rows if r["kind"] == "A3" and r["hyst"] == setting["hyst"] and r["ttt"] == setting["ttt"]]


def select_eta(rows, out=OUT):
    """Among the candidates whose mobility-failure rate does not exceed the budget (the
    failure rate of A3 with 3 dB and 0.3 s), take the one with the fewest unnecessary
    handovers per user-minute; if none meets the budget, the one with the lowest failure
    rate.  Writes tuned_eta.json."""
    t = [r for r in rows if r["block"] == "tune"]
    mean = lambda rs, k: float(np.mean([r[k] for r in rs]))
    budget = mean(a3_rows(t, BUDGET), "fail_pm")
    tab = {}
    for e in ETAS:
        rs = [r for r in t if r["kind"] == "Mem" and r["eta"] == e]
        tab[e] = (mean(rs, "UHO_pm"), mean(rs, "fail_pm"))
    ok = [e for e in ETAS if tab[e][1] <= budget] or [min(ETAS, key=lambda e: tab[e][1])]
    eta = min(ok, key=lambda e: tab[e][0])
    with open(os.path.join(out, "tuned_eta.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(dict(eta=eta, budget=budget, candidates={str(e): tab[e] for e in ETAS},
                       control=(mean(a3_rows(t, CONTROL), "UHO_pm"), mean(a3_rows(t, CONTROL), "fail_pm"))),
                  fh, indent=1)
        fh.write("\n")
    return eta


# ----------------------------------------------------------------------------
# runner
# ----------------------------------------------------------------------------
def read_rows(out=OUT):
    """Finished runs by job id."""
    done = {}
    path = os.path.join(out, "runs.jsonl")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                r = json.loads(line); done[r["id"]] = r
    return done


def run(jobs, out=OUT, procs=None, label=""):
    """Run the jobs that have no row in runs.jsonl yet and return the rows of all jobs.
    Every finished run is appended at once, so an interrupted call can simply be repeated."""
    os.makedirs(out, exist_ok=True)
    done = read_rows(out)
    todo = [j for j in jobs if j["id"] not in done]
    print(f"[{label}] {len(jobs)} jobs, {len(todo)} to run", flush=True)
    t0 = time.time()
    if todo:
        with Pool(procs or n_procs()) as pool, \
                open(os.path.join(out, "runs.jsonl"), "a", encoding="utf-8", newline="\n") as fh:
            for i, r in enumerate(pool.imap_unordered(partial(run_job, out=out), todo, chunksize=1)):
                fh.write(json.dumps(r) + "\n"); fh.flush(); done[r["id"]] = r
                if (i + 1) % 20 == 0 or i + 1 == len(todo):
                    print(f"[{label}] {i + 1}/{len(todo)}  {time.time() - t0:.0f}s", flush=True)
    return [done[j["id"]] for j in jobs]


def tuned_eta(out=OUT):
    """The selected eta: from tuned_eta.json, else from the validation rows if they are complete."""
    path = os.path.join(out, "tuned_eta.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)["eta"]
    done = read_rows(out)
    if all(j["id"] in done for j in stage_tune()):
        return select_eta([done[j["id"]] for j in stage_tune()], out)
    raise SystemExit("The validation runs are not complete: run 'python experiments/run_study.py' first.")


def analysis_logs(jobs):
    """The jobs whose event log experiments/analyze.py reads: the long control runs."""
    return [j for j in jobs if j["log"] and j["T"] == T_LOG]


def status():
    """Print what is done and what is missing."""
    done = read_rows()
    tune = stage_tune()
    print(f"results directory: {OUT}")
    print(f"validation runs:   {sum(j['id'] in done for j in tune)}/{len(tune)}")
    if not all(j["id"] in done for j in tune):
        print("test runs:         the job list depends on the selected eta, which needs the validation runs")
        return
    main = stage_main(tuned_eta())
    need = analysis_logs(main)
    print(f"selected eta:      {tuned_eta()} dB")
    print(f"test runs:         {sum(j['id'] in done for j in main)}/{len(main)}")
    print(f"event logs read by the analysis: {sum(os.path.exists(log_path(j['id'])) for j in need)}/{len(need)}")
    unknown = set(done) - {j["id"] for j in tune + main}
    if unknown:
        print(f"rows that belong to no job of the study: {len(unknown)}")


def rebuild_logs(every=False):
    """Re-create missing event logs by repeating their control runs.  The rows in runs.jsonl
    stay as they are; each repeated run is compared with its row (the runs are deterministic).
    By default only the logs that the analysis reads; every=True also those of the short runs."""
    done = read_rows()
    jobs = stage_main(tuned_eta())
    jobs = [j for j in jobs if j["log"]] if every else analysis_logs(jobs)
    todo = [j for j in jobs if not os.path.exists(log_path(j["id"]))]
    print(f"[logs] {len(jobs)} event logs, {len(todo)} to re-create", flush=True)
    t0 = time.time(); bad = 0
    if todo:
        with Pool(n_procs()) as pool:
            for i, r in enumerate(pool.imap_unordered(run_job, todo, chunksize=1)):
                old = done.get(r["id"])
                if old is None:
                    with open(os.path.join(OUT, "runs.jsonl"), "a", encoding="utf-8", newline="\n") as fh:
                        fh.write(json.dumps(r) + "\n")
                elif any(r[k] != old[k] for k in COUNTS + ("n_events",)):
                    bad += 1
                    print(f"[logs] {r['id']}: differs from its row in runs.jsonl "
                          f"({', '.join(f'{k} {r[k]} vs {old[k]}' for k in COUNTS)})", flush=True)
                if (i + 1) % 20 == 0 or i + 1 == len(todo):
                    print(f"[logs] {i + 1}/{len(todo)}  {time.time() - t0:.0f}s", flush=True)
    if bad:
        print(f"[logs] {bad} repeated runs do not reproduce their stored row: the library versions probably "
              "differ from requirements.txt; the new logs then do not belong to the rows in runs.jsonl")
    else:
        print("[logs] done; every repeated run reproduced its row in runs.jsonl")


def smoke():
    """Four runs of 30 s through the whole chain: simulator, both rules, private shadowing,
    event log and repeatability index.  Results go to results/smoke/ and are not kept."""
    out = os.path.join(OUT, "smoke")
    os.makedirs(out, exist_ok=True)
    if os.path.exists(os.path.join(out, "runs.jsonl")):
        os.remove(os.path.join(out, "runs.jsonl"))
    jobs = [J("smoke", "highway", 1, A3C, T=30.0, log=True, phi=0.5),
            J("smoke", "highway", 1, mem(eta=8.0), T=30.0, warm=30.0, phi=0.5),
            J("smoke", "street", 1, A3C, T=30.0),
            J("smoke", "street", 1, mem(eta=0.0), T=30.0, warm=30.0)]
    rows = run(jobs, out=out, procs=min(4, n_procs()), label="smoke")
    print(f"\n{'profile':<9}{'phi':>5}  {'rule':<16}{'HO':>6}{'unnec.':>8}{'failed':>8}{'UHO_pm':>9}{'fail_pm':>9}{'time':>7}")
    for r in rows:
        rule = "A3 (control)" if r["kind"] == "A3" else f"memory, eta={r['eta']:g}"
        print(f"{r['profile']:<9}{r['phi']:>5}  {rule:<16}{r['HO']:>6}{r['unnecessary']:>8}{r['failed']:>8}"
              f"{r['UHO_pm']:>9.2f}{r['fail_pm']:>9.2f}{r['secs']:>6.0f}s")
    same = all(rows[2][k] == rows[3][k] for k in COUNTS)
    print("\nmemory rule with eta = 0 equals the control (street):", "yes" if same else "NO")
    rep = repeatability(*load_log(log_path(jobs[0]["id"], out)))
    print(f"event log of the highway control run: {rep['events']} events in {rep['groups']} places, "
          f"rho = {rep['rho']:.2f}, skill = {rep['skill']:.2f}")
    print("smoke test passed" if same else "smoke test FAILED")
    return 0 if same else 1


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "smoke":
        sys.exit(smoke())
    elif cmd == "status":
        status()
    elif cmd == "logs":
        rebuild_logs(every=len(sys.argv) > 2 and sys.argv[2] == "all")
    elif cmd == "all":
        eta = select_eta(run(stage_tune(), label="tune"))
        print("selected eta =", eta, flush=True)
        run(stage_main(eta), label="main")
        print("study finished; next: python experiments/analyze.py", flush=True)
    else:
        sys.exit(f"unknown command {cmd!r}; use one of: smoke, status, logs  (no argument: run the study)")
