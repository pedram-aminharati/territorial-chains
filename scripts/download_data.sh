#!/usr/bin/env bash
# Fetch the open data eqasim-france v1.5.0 needs for Loire-Atlantique (44),
# population synthesis only. Run inside WSL from the pilot folder:
#
#   bash scripts/download_data.sh
#
# Files already present are skipped and interrupted downloads resume, so the
# script can be re-run safely. Sources are the official publishers: INSEE,
# IGN (data.geopf.fr), data.gouv.fr, adresse.data.gouv.fr and the transport
# ministry's statistics site. Expect several GB in total.
set -uo pipefail

PILOT="$(cd "$(dirname "$0")/.." && pwd)"
DATA="$PILOT/data"
UA="Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0"
FAILED=()

fetch() {   # fetch <url> <path relative to data/>
  local url="$1" target="$DATA/$2"
  mkdir -p "$(dirname "$target")"
  if [ -s "$target" ] && [ ! -e "$target.part" ]; then
    echo "have   $2"
    return
  fi
  echo "get    $2"
  if wget -c -q --show-progress --user-agent="$UA" -O "$target.part" "$url"; then
    mv "$target.part" "$target"
  else
    echo "FAILED $2"
    FAILED+=("$2  <-  $url")
  fi
}

INSEE="https://www.insee.fr/fr/statistiques/fichier"
MIN="https://www.statistiques.developpement-durable.gouv.fr/media"
GOUV="https://www.data.gouv.fr/api/1/datasets/r"
IGN="https://data.geopf.fr/telechargement/download"

# Census 2022: individuals, population totals, commuting flows
fetch "$INSEE/8647104/RP2022_indcvi.parquet"                      rp_2022/RP2022_indcvi.parquet
fetch "$INSEE/8647014/base-ic-evol-struct-pop-2022_csv.zip"       rp_2022/base-ic-evol-struct-pop-2022_csv.zip
fetch "$INSEE/8589904/RP2022_mobpro.parquet"                      rp_2022/RP2022_mobpro.parquet
fetch "$INSEE/8589945/RP2022_mobsco.parquet"                      rp_2022/RP2022_mobsco.parquet

# Income (Filosofi 2021), facilities (BPE 2025), zoning registry, urban units
fetch "$INSEE/7756855/indic-struct-distrib-revenu-2021-COMMUNES_XLSX.zip"  filosofi_2021/indic-struct-distrib-revenu-2021-COMMUNES_XLSX.zip
fetch "$INSEE/7756855/indic-struct-distrib-revenu-2021-SUPRA_XLSX.zip"     filosofi_2021/indic-struct-distrib-revenu-2021-SUPRA_XLSX.zip
fetch "$INSEE/8217525/BPE25.parquet"                              bpe_2025/BPE25.parquet
fetch "$INSEE/7708995/reference_IRIS_geo2024.zip"                 codes_2024/reference_IRIS_geo2024.zip
fetch "$INSEE/4802589/UU2020_au_01-01-2026.zip"                   urban_type/UU2020_au_01-01-2026.zip

# IRIS contours (IGN)
fetch "$IGN/CONTOURS-IRIS/CONTOURS-IRIS_3-0__GPKG_LAMB93_FXX_2024-01-01/CONTOURS-IRIS_3-0__GPKG_LAMB93_FXX_2024-01-01.7z" \
      iris_2024/CONTOURS-IRIS_3-0__GPKG_LAMB93_FXX_2024-01-01.7z

# Enterprise register (SIRENE): establishments, legal units, geolocation
fetch "$GOUV/a29c1297-1f92-4e2a-8f6b-8c902ce96c5f"  sirene/stock-stocketablissement-parquet.parquet
fetch "$GOUV/350182c9-148a-46e0-8389-76c2ec1374a3"  sirene/stock-stockunitelegale-parquet.parquet
fetch "$GOUV/672007af-0146-491f-835c-8314d63fa44e"  sirene/geoloc-geolocalisationetablissement-sirene-pour-etudes-statistiques-parquet.parquet

# Buildings (BD TOPO) and addresses (BAN) for Loire-Atlantique
fetch "$IGN/BDTOPO/BDTOPO_3-0_TOUSTHEMES_GPKG_LAMB93_D044_2022-03-15/BDTOPO_3-0_TOUSTHEMES_GPKG_LAMB93_D044_2022-03-15.7z" \
      bdtopo_nantes/BDTOPO_3-0_TOUSTHEMES_GPKG_LAMB93_D044_2022-03-15.7z
fetch "https://adresse.data.gouv.fr/data/ban/adresses/latest/csv/adresses-44.csv.gz"  ban_nantes/adresses-44.csv.gz

# Household travel surveys (skipped when already in place)
fetch "$MIN/2339/download"  entd_2008/Q_tcm_menage_0.csv
fetch "$MIN/2555/download"  entd_2008/Q_tcm_individu.csv
fetch "$MIN/2556/download"  entd_2008/Q_menage.csv
fetch "$MIN/2565/download"  entd_2008/Q_individu.csv
fetch "$MIN/2566/download"  entd_2008/Q_ind_lieu_teg.csv
fetch "$MIN/2567/download"  entd_2008/K_mobilite.csv
fetch "$MIN/2568/download"  entd_2008/K_deploc.csv
fetch "$MIN/5052/download"  emp_2019/emp_2019_donnees_individuelles_anonymisees_novembre2024.zip

echo
echo "Data folder:"
du -sh "$DATA"/* 2>/dev/null
if [ ${#FAILED[@]} -gt 0 ]; then
  echo
  echo "These downloads failed (re-run the script, or fetch them in a browser):"
  printf '  %s\n' "${FAILED[@]}"
  exit 1
fi
echo
echo "All inputs present."
