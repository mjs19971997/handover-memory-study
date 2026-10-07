# Synthetic layout

`realistic_5G_2x.csv` is a synthetic dense-urban drive-test table with 40 cells, created by
the authors and distributed under the licence of this repository.  It is the only radio
layout the study uses; its environment name in the code and in the result files is `UDN-40`.

| File | Environment name | Cells | Samples |
|---|---|---|---|
| `realistic_5G_2x.csv` | `UDN-40` | 40 | 20000 |

Columns: `Lon, Lat, RSRP, RSRQ, CINR, PCI, Height (m), Distance (m), Azimuth, Elevation, Speed (m/s)`.
The simulator uses `Lon`, `Lat`, `RSRP`, `PCI`, `Distance (m)` and `Azimuth` to estimate the
cell positions and a per-cell path-loss model (`hosim/radiomap.py`).
