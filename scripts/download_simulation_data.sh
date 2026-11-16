#!/usr/bin/env bash
# Fetch what the MATSim step needs on top of the population data: the road
# network extract and the public-transport timetables for Loire-Atlantique.
# Run inside WSL from the pilot folder:
#
#   bash scripts/download_simulation_data.sh
#
# Sources (the ones eqasim's Nantes case lists, docs/cases/nantes.md):
#   OpenStreetMap extract   download.geofabrik.de            about 350 MB
#   GTFS timetables         transport.data.gouv.fr           about 150 MB in total
#     Naolib (Nantes), Aléop (regional coaches), Ycéo (Saint-Nazaire),
#     Lila Presqu'île (Guérande), Brévibus (Saint-Brevin), SNCF (TGV, Intercités, TER)
#
# The timetables are the ones in force on the day of the download; the date is
# written to data/gtfs_nantes/DOWNLOADED.txt so the run can be described exactly.
# eqasim cuts both the network and the timetables to the département itself.
# Files already present are skipped; interrupted downloads resume.
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

GOUV="https://www.data.gouv.fr/api/1/datasets/r"

fetch "https://download.geofabrik.de/europe/france/pays-de-la-loire-latest.osm.pbf"  osm_nantes/pays-de-la-loire-latest.osm.pbf

fetch "$GOUV/65bdd7e4-a8e7-4a54-893a-808e71c34d68"                gtfs_nantes/naolib.gtfs.zip
fetch "$GOUV/916752e4-5daa-48bd-8bc1-4dd8d64f1d4a"                gtfs_nantes/aleop.gtfs.zip
fetch "$GOUV/a1867718-7921-42a6-b672-c53b8c583aa3"                gtfs_nantes/yceo.gtfs.zip
fetch "https://transport.data.gouv.fr/resources/83762/download"   gtfs_nantes/lilapresquile.gtfs.zip
fetch "$GOUV/b8d1007f-567e-48c4-9c40-bee205f1e688"                gtfs_nantes/brevibus.gtfs.zip
fetch "$GOUV/9ae758ec-cd7a-40cd-a890-bb3963224942"                gtfs_nantes/sncf-tgv-intercite-ter.gtfs.zip

[ -f "$DATA/gtfs_nantes/DOWNLOADED.txt" ] || date '+%Y-%m-%d' > "$DATA/gtfs_nantes/DOWNLOADED.txt"

echo
echo "--- checking the timetable archives"
python3 - "$DATA/gtfs_nantes" <<'EOF'
import sys, zipfile, pathlib
needed = {"stops.txt", "routes.txt", "trips.txt", "stop_times.txt", "agency.txt"}
bad = 0
for path in sorted(pathlib.Path(sys.argv[1]).glob("*.zip")):
    try:
        names = {pathlib.PurePosixPath(n).name for n in zipfile.ZipFile(path).namelist()}
    except zipfile.BadZipFile:
        print("NOT A ZIP  %s  (delete it and run the script again)" % path.name); bad += 1; continue
    missing = sorted(needed - names)
    calendar = bool({"calendar.txt", "calendar_dates.txt"} & names)
    status = "ok" if not missing and calendar else "INCOMPLETE, missing %s" % (missing or "calendar")
    bad += status != "ok"
    print("%-9s  %-36s %6.1f MB" % (status[:9], path.name, path.stat().st_size / 1e6), "" if status == "ok" else status)
sys.exit(1 if bad else 0)
EOF
CHECK=$?

echo
if [ ${#FAILED[@]} -eq 0 ] && [ $CHECK -eq 0 ]; then
  echo "All simulation inputs are in place."
else
  [ ${#FAILED[@]} -gt 0 ] && { echo "Not downloaded:"; printf '  %s\n' "${FAILED[@]}"; }
  [ $CHECK -ne 0 ] && echo "One or more timetable archives look wrong (see above)."
  exit 1
fi
