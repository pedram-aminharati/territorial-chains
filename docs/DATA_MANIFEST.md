# Data manifest

All files are open data from official French sources. Target folders are
relative to `data/`. Sizes marked "page" were read from the
download page on 12 Nov 2026; the others are confirmed before each download.

## Phase A: surveys (enough for work packages 1, 2 and 4)

| File | Size | Source | Folder |
|---|---|---|---|
| Données individuelles anonymisées EMP 2019 (zip) | 6.57 Mo (page) | statistiques.developpement-durable.gouv.fr, media 5052 | `emp_2019/` saved as `emp_2019_donnees_individuelles_anonymisees_novembre2024.zip` |
| Dictionnaire des données EMP 2019 (xlsx) | 217 Ko (page) | same page, media 5051 | `emp_2019/doc/` |
| ENTD 2008 ménages, `Q_tcm_menage_0.csv` | 9.63 Mo (page) | ENTD 2008 page, media 2339 | `entd_2008/` |
| ENTD 2008 individus, `Q_tcm_individu.csv` | 17.91 Mo (page) | media 2555 | `entd_2008/` |
| ENTD 2008 logement/véhicules, `Q_menage.csv` | 8.05 Mo (page) | media 2556 | `entd_2008/` |
| ENTD 2008 domicile-travail, `Q_individu.csv` | 16.34 Mo (page) | media 2565 | `entd_2008/` |
| ENTD 2008 mobilité contrainte, `Q_ind_lieu_teg.csv` | 13.9 Mo (page) | media 2566 | `entd_2008/` |
| ENTD 2008 mobilité quotidienne, `K_mobilite.csv` | 6.68 Mo (page) | media 2567 | `entd_2008/` |
| ENTD 2008 déplacements locaux, `K_deploc.csv` | 61.28 Mo (page) | media 2568 | `entd_2008/` |

The mapping of ENTD page titles to file names is to be checked against the
downloaded names; eqasim expects exactly the names above.

## Phase B: pipeline inputs for departement 44 (work package 3)

| Dataset | Source | Folder |
|---|---|---|
| RP 2022 individus `RP2022_indcvi.parquet` | insee.fr/fr/statistiques/8647104 | `rp_2022/` |
| RP 2022 population totals `base-ic-evol-struct-pop-2022_csv.zip` | insee.fr/fr/statistiques/8647014 | `rp_2022/` |
| RP 2022 `RP2022_mobpro.parquet`, `RP2022_mobsco.parquet` | insee.fr 8589904, 8589945 | `rp_2022/` |
| Filosofi 2021, communes and supra zips | insee.fr/fr/statistiques/7756855 | `filosofi_2021/` |
| BPE 2025 `BPE25.parquet` | insee.fr/fr/statistiques/8217525 | `bpe_2025/` |
| IRIS contours 2024 (7z) | data.geopf.fr (IGN) | `iris_2024/` |
| Zoning registry `reference_IRIS_geo2024.zip` | insee.fr/fr/information/7708995 | `codes_2024/` |
| SIRENE establishments, legal units, geolocation | data.gouv.fr | `sirene/` |
| BD TOPO departement 44 (7z) | geoservices.ign.fr/bdtopo | `bdtopo_nantes/` |
| BAN `adresses-44.csv.gz` | adresse.data.gouv.fr | `ban_nantes/` |
| Urban units `UU2020_au_01-01-2024.zip` | insee.fr | `urban_type/` |
| EDGT Loire-Atlantique 2015, three txt files | data.loire-atlantique.fr | `edgt_44_2015/` |

SIRENE and the census file are national and large (several GB together).
A first run at `sampling_rate: 0.001` fails fast on any missing input.
