#!/usr/bin/env bash
# Fetch the regional household travel survey of Loire-Atlantique (EDGT 2015), open data
# of the Département (Licence Ouverte), for variant F. Run inside WSL from the pilot folder:
#
#   bash scripts/download_edgt.sh
#
# Three archives, 26 MB in total: the raw survey files, the documentation and the
# open-data package. They are unpacked next to each other and the three files eqasim
# reads are copied to data/edgt_44_2015/.
set -uo pipefail

PILOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$PILOT/data/edgt_44_2015"
BASE="https://data.loire-atlantique.fr/api/explore/v2.1/catalog/datasets/224400028_enquete-deplacements-en-loire-atlantique/attachments"
mkdir -p "$TARGET" && cd "$TARGET" || exit 1

for pair in "donnees_EDGT44_2015.zip=donnees_edgt44_2015_zip" \
            "3_Documents_explicatifs.zip=3_documents_explicatifs_zip" \
            "Enquete_deplacements_opendata.zip=enquete_deplacements_opendata_zip"; do
  file="${pair%%=*}"; id="${pair#*=}"
  if [ -s "$file" ]; then echo "have   $file"; else echo "get    $file"; wget -q --show-progress -O "$file" "$BASE/$id" || echo "FAILED $file"; fi
done

python3 - <<'PY'
import glob, zipfile
for archive in sorted(glob.glob("*.zip")):
    try:
        zipfile.ZipFile(archive).extractall(archive[:-4])
    except zipfile.BadZipFile:
        print("NOT A ZIP", archive)
PY
find . -name '02[abc]_EDGT_44_*.txt' -not -path './02*' -exec cp -n {} . \;

echo
echo "--- unpacked files"
find . -mindepth 2 -type f | sort | head -150
echo
echo "--- files eqasim reads"
ls -la 02a_EDGT_44_MENAGE_FAF_TEL_2015-08-07_modifZF.txt 02b_EDGT_44_PERSO_FAF_TEL_ModifPCS_2016-04-14.txt 02c_EDGT_44_DEPLA_FAF_TEL_DIST_2015-11-10.txt
