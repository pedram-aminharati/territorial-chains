# Simulation step (MATSim)

Goal: see whether the matching design still matters once the population is
simulated. Variants A (eqasim defaults) and C (urban type added) are simulated
with the same road network, the same timetables and the same mode-choice
parameters, so any difference between them comes from the activity chains.

## What it needs

| | |
|---|---|
| Java | a **JDK 25**. eqasim-france v1.5.0 only checks for Java 17, but the eqasim-java commit it pins (`fc85693`) is compiled for Java 25. |
| Maven, git, fontconfig | Maven builds pt2matsim 26.1 and eqasim-java 2.2.0 inside the pipeline. |
| Road network | OpenStreetMap extract of Pays de la Loire (Geofabrik), cut to the département by eqasim. |
| Timetables | Six GTFS feeds from transport.data.gouv.fr: Naolib, Aléop, Ycéo, Lila Presqu'île, Brévibus, SNCF. |

## Run

```bash
cd /path/to/territorial-chains            # for instance /mnt/c/Users/<you>/Downloads/territorial-chains
bash scripts/setup_simulation.sh                 # once: Java 25 JDK, Maven, fontconfig
bash scripts/download_simulation_data.sh         # once: network extract and timetables
(cd ~/eqasim-france && uv run python "$OLDPWD/configs/make_configs.py" "$OLDPWD" 0.1)

ITERATIONS=2 bash scripts/run_simulation.sh smoke_sim                  # toolchain test on the 0.1% sample
bash scripts/run_simulation.sh A_entd_local_sim C_entd_urban_sim       # the two real runs
```

`run_simulation.sh` first runs the eqasim stages `synthesis.output` and
`matsim.output` (scenario files plus a two-iteration test), then starts
`org.eqasim.ile_de_france.RunSimulation` from the jar eqasim wrote, with a cap
of 60 iterations. eqasim's own termination rule stops the run earlier once the
mode shares are stable. Results are copied to `output/<variant>/simulation/`.

## Score

```bash
python scripts/evaluate_simulation.py output/A_entd_local_sim data/urban_type/UU2020_au_01-01-2026.zip
python scripts/evaluate_simulation.py output/C_entd_urban_sim data/urban_type/UU2020_au_01-01-2026.zip
```

Each call writes `sim_modes.csv`, `sim_travel.csv` and `sim_convergence.csv`
to `results/<variant>/`: mode shares, and trips, kilometres, car kilometres
and minutes per resident, by urban type of the home commune.

## How to read it

- eqasim's mode-choice model is calibrated for Île-de-France. Levels are not a
  forecast for Loire-Atlantique; only A-against-C differences are interpreted.
- Timetables are those in force on the download day (see
  `data/gtfs_nantes/DOWNLOADED.txt`), not those of the census year.
- One random seed, 10% sample. A difference is reported as such only if it is
  larger than what a second seed produces.

## Results (12 November 2026, one seed, 10% sample)

Both runs were stopped by eqasim's convergence rule, A after 60 iterations and C after 57.
Each simulated the population it was built from: persons and donors are identical to the
earlier A and C runs, and 96% of persons have the same number of trips in the simulation
output as in the population. The rest are agents that never finish their day: when the last
iteration ends at 30:00, 4,830 agents in A and 4,592 in C are still under way and none was
removed, which accounts for 95% of the persons with missing trips (5,089 and 4,819). Their
last recorded trip starts around noon. What holds them was not identified
(`results/<variant>_sim/sim_unfinished.csv`, note 6 in `docs/UPSTREAM_NOTES.md`).
In C, 105 matched persons whose household has no home commune are left out.

| Per resident | Variant | Central city | Suburb | Isolated city | Rural | All |
|---|---|---:|---:|---:|---:|---:|
| Trips per resident | A | 3.40 | 3.63 | 3.71 | 3.71 | 3.58 |
| Trips per resident | C | 3.27 | 3.28 | 3.17 | 3.06 | 3.22 |
| Km per resident | A | 21.5 | 26.9 | 35.6 | 39.5 | 28.7 |
| Km per resident | C | 20.3 | 27.9 | 35.4 | 38.1 | 28.3 |
| Car km per resident | A | 12.7 | 17.7 | 23.3 | 26.1 | 18.4 |
| Car km per resident | C | 12.2 | 17.8 | 24.0 | 25.3 | 18.2 |
| Minutes per resident | A | 70 | 74 | 89 | 99 | 79 |
| Minutes per resident | C | 67 | 73 | 84 | 91 | 76 |
| Km per trip | A | 6.3 | 7.4 | 9.6 | 10.6 | 8.0 |
| Km per trip | C | 6.2 | 8.5 | 11.2 | 12.4 | 8.8 |

What changes between A and C is how often people travel: rural residents make 18% fewer trips
in C. What does not change much is how far they drive: car kilometres per resident differ by
-2.9% in rural communes and -0.7% overall. With one seed, differences of that size cannot be
told apart from noise; over three seeds they keep their sign (`docs/SEEDS.md`).

A warning sign for the levels: the Île-de-France mode-choice model gives rural residents a higher
bike share than central-city residents. Only A-against-C differences are used.
