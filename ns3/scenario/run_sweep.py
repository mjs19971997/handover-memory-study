# -*- coding: utf-8 -*-
"""Run the eta sweep of the location-memory study, resumable. Standard library only.

    python run_sweep.py            run / resume (folders mem_urban and mem_base next to this file)
    python run_sweep.py --status   how many runs are finished
    python run_sweep.py --smoke    a few-minute test with tiny sizes (folder smoke/)

Design: rule "mem" with h = 4 dB and TTT 100 ms; eta = 0 (the A3 control), 6, 12, 24, 36 dB;
two environments (urban, base); nominal inter-site distance 200 and 400 m; speeds 8, 16 and
30 m/s; seeds 1 to 6; 900 s per run with the first 60 s discarded; 20 UEs, light traffic.
360 runs. Within a seed all eta levels see the same trajectories and random streams.

Every run appends one row to results.csv of its folder and leaves its per-attempt and
per-failure files in res/. A run whose id is already in results.csv is skipped. A failed run
is retried once and then listed in failed_jobs.txt. Workers: environment variable NS3_WORKERS
(default: logical CPUs minus 4). The program must have been built with build_scenario.sh.
"""
import csv
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
SMOKE = "--smoke" in sys.argv
ROOT = os.path.join(HERE, "smoke") if SMOKE else HERE
NS3 = os.environ.get("NS3_DIR_WIN", r"C:\cl\tools\ns3\ns-3-dev")
EXE_SRC = os.path.join(NS3, "build", "scratch", "ns3.48-a3-scenario-optimized.exe")
EXE = os.path.join(ROOT, "bin", "a3-scenario.exe")
DLL_PATH = os.path.join(NS3, "build", "lib") + ";" + r"C:\cl\tools\msys64\ucrt64\bin"
WORKERS = int(os.environ.get("NS3_WORKERS", str(max(1, (os.cpu_count() or 8) - 4))))
RUN_FLAGS = 0x08000000 | 0x00004000 if os.name == "nt" else 0      # no window, below-normal priority

H_DB, TTT_MS = 4, 100
ETAS = [0, 6, 12, 24, 36]
CELLS = [(isd, v) for isd in (200, 400) for v in (8, 16, 30)]
SEEDS = list(range(1, 7))
T_SIM, DISCARD, N_UE = 900.0, 60.0, 20
if SMOKE:
    ETAS, CELLS, SEEDS, T_SIM, DISCARD = [0, 24], [(400, 16)], [1], 20.0, 4.0

_lock = threading.Lock()


def jobs(scen):
    folder = "mem_" + scen
    res = os.path.join(ROOT, folder, "res").replace("\\", "/")
    out = []
    for seed in SEEDS:
        for isd, v in CELLS:
            for eta in ETAS:
                jid = "mem_mem_e%d_d%d_v%d_s%d" % (eta, isd, v, seed)
                args = ["--rule=mem", "--hyst=%d" % H_DB, "--ttt=%d" % TTT_MS, "--memEta=%d" % eta] + \
                       (["--scen=urban"] if scen == "urban" else []) + \
                       ["--isd=%d" % isd, "--speed=%d" % v, "--rngRun=%d" % seed, "--simTime=%g" % T_SIM,
                        "--discard=%g" % DISCARD, "--nUe=%d" % N_UE, "--udpInterval=100", "--fading=0",
                        "--events=1", "--tag=%s" % jid, "--outDir=%s" % res]
                out.append(dict(id=jid, folder=folder, label="mem_e%d" % eta,
                                config="h%d_t%d_eta%d" % (H_DB, TTT_MS, eta), args=args))
    return out


def read_results(folder):
    p = os.path.join(ROOT, folder, "results.csv")
    if not os.path.exists(p):
        return []
    with open(p, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_result(job, metrics):
    row = dict(job_id=job["id"], phase="mem", label=job["label"], config=job["config"])
    row.update(metrics)
    p = os.path.join(ROOT, job["folder"], "results.csv")
    with _lock:
        new = not os.path.exists(p)
        header = list(row.keys())
        if not new:
            with open(p, newline="", encoding="utf-8") as f:
                header = next(csv.reader(f))
        with open(p, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore")
            if new:
                w.writeheader()
            w.writerow(row)


def run_one(job):
    env = dict(os.environ)
    env["PATH"] = DLL_PATH + ";" + env.get("PATH", "")
    fdir = os.path.join(ROOT, job["folder"])
    jpath = os.path.join(fdir, "res", job["id"] + ".json")
    for attempt in (1, 2):
        if os.path.exists(jpath):
            os.remove(jpath)
        with open(os.path.join(fdir, "logs", job["id"] + ".log"), "w", encoding="utf-8") as lf:
            rc = subprocess.run([EXE] + job["args"], stdout=lf, stderr=subprocess.STDOUT, env=env, cwd=fdir,
                                creationflags=RUN_FLAGS).returncode
        if rc == 0 and os.path.exists(jpath):
            with open(jpath, encoding="utf-8") as f:
                append_result(job, json.load(f))
            return True
        print("FAILED %s/%s (attempt %d, exit code %s)" % (job["folder"], job["id"], attempt, rc), flush=True)
    with _lock:
        with open(os.path.join(fdir, "failed_jobs.txt"), "a", encoding="utf-8") as f:
            f.write(job["id"] + "\n")
    return False


def main():
    alljobs = jobs("urban") + jobs("base")
    done = {f: {r["job_id"] for r in read_results(f)} for f in ("mem_urban", "mem_base")}
    todo = [j for j in alljobs if j["id"] not in done[j["folder"]]]
    if "--status" in sys.argv:
        print("%d of %d runs finished" % (len(alljobs) - len(todo), len(alljobs)))
        return
    for f in ("mem_urban", "mem_base"):
        for d in ("res", "logs"):
            os.makedirs(os.path.join(ROOT, f, d), exist_ok=True)
    os.makedirs(os.path.dirname(EXE), exist_ok=True)
    shutil.copy2(EXE_SRC, EXE)              # one frozen program copy for the whole sweep
    print("%d runs, %d already finished, %d to run, %d at a time" % (len(alljobs), len(alljobs) - len(todo),
                                                                     len(todo), WORKERS), flush=True)
    t0 = time.time()
    state = dict(n=0, fail=0)

    def work(job):
        ok = run_one(job)
        with _lock:
            state["n"] += 1
            state["fail"] += (not ok)
            n = state["n"]
        if n % 10 == 0 or n == len(todo):
            el = time.time() - t0
            print("%s %d/%d finished, %d failed, about %.1f h left"
                  % (time.strftime("%H:%M:%S"), n, len(todo), state["fail"], el / n * (len(todo) - n) / 3600.0), flush=True)

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(work, todo))
    print("done: %d run, %d failed, %.2f h" % (state["n"], state["fail"], (time.time() - t0) / 3600.0))


if __name__ == "__main__":
    main()
