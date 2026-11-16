# Repeats over random seeds

Every result so far comes from one random seed. Following Hörl and Balac (2021),
variants A and C are generated again with other seeds and results are reported
as a mean with its range. A repeat redraws the 10% census sample, the matching
and the locations, so the range covers all three sources of sampling noise.

| Seed | `random_seed` | Population | MATSim |
|---|---|---|---|
| 1 | 1234 | done | done |
| 2 | 2234 | `A_entd_local_seed2_sim`, `C_entd_urban_seed2_sim` | yes |
| 3 | 3234 | `A_entd_local_seed3_sim`, `C_entd_urban_seed3_sim` | yes |
| 4 | 4234 | `A_entd_local_seed4`, `C_entd_urban_seed4` | no |
| 5 | 5234 | `A_entd_local_seed5`, `C_entd_urban_seed5` | no |

```bash
cd /path/to/territorial-chains            # for instance /mnt/c/Users/<you>/Downloads/territorial-chains
(cd ~/eqasim-france && uv run python "$OLDPWD/configs/make_configs.py" "$OLDPWD" 0.1)
bash scripts/run_seeds.sh                    # all of the table above, an overnight job
SIM_SEEDS="" bash scripts/run_seeds.sh       # populations only
```

Five populations per variant give a range for every population result; three
simulations per variant give one for the simulated quantities. A failed run
does not stop the others, and `output/seeds.log` ends with a summary.

## Results (13 November 2026)

All eight runs finished. Mean over seeds, with the lowest and highest seed in brackets.

Share of residents staying home (5 seeds):

| | Central | Suburb | Isolated | Rural |
|---|---|---|---|---|
| A | 0.095 (0.093 to 0.096) | 0.091 (0.089 to 0.092) | 0.088 (0.088 to 0.090) | 0.088 (0.085 to 0.089) |
| C | 0.106 (0.104 to 0.108) | 0.111 (0.108 to 0.113) | 0.146 (0.144 to 0.150) | 0.168 (0.165 to 0.171) |

Hellinger distance to the survey (5 seeds):

| | Central | Suburb | Isolated | Rural |
|---|---|---|---|---|
| A | 0.088 (0.087 to 0.090) | 0.076 (0.075 to 0.078) | 0.118 (0.116 to 0.121) | 0.129 (0.126 to 0.133) |
| C | 0.054 (0.053 to 0.056) | 0.065 (0.064 to 0.066) | 0.054 (0.051 to 0.055) | 0.045 (0.042 to 0.047) |

Change from A to C in the simulation, computed seed by seed (3 seeds):

| | Central | Suburb | Isolated | Rural | All |
|---|---|---|---|---|---|
| Trips per resident | -3.5% (-3.7 to -3.3) | -9.5% (-9.6 to -9.5) | -15.2% (-15.7 to -14.5) | -18.1% (-18.7 to -17.5) | -10.1% (-10.3 to -9.9) |
| Car km per resident | -4.8% (-5.8 to -4.1) | +1.4% (+0.6 to +2.7) | +2.4% (+1.5 to +3.0) | -3.5% (-3.8 to -2.9) | -0.8% (-1.5 to -0.2) |
| Km per trip | -3.2% (-4.5 to -2.3) | +14.7% (+13.9 to +15.5) | +16.5% (+16.0 to +17.3) | +17.3% (+16.9 to +17.6) | +9.6% (+9.1 to +9.8) |

The population results do not depend on the seed. In the simulation, the fall in trips is the
same in every seed. Car kilometres differ by a few percent by territory, with the same sign in
all three seeds, and by less than 1.5% over the département. Three simulations per variant are
few: the direction is established, the size only roughly.

Tables: `results/seeds/summary.csv`, `differences.csv`, `by_seed.csv` (`scripts/summarise_seeds.py`).
