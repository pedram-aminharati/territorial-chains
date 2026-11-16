#!/usr/bin/env bash
# Tools for the MATSim step. Run once inside WSL (Ubuntu), from the pilot folder:
#
#   bash scripts/setup_simulation.sh
#
# eqasim-france v1.5.0 builds two Java programs itself with Maven: pt2matsim
# (network and timetable conversion) and eqasim-java (the simulation). Its own
# check only asks for Java 17, but the eqasim-java commit it pins (fc85693)
# is compiled for Java 25, so a Java 25 *JDK* is needed, not a JRE.
set -euo pipefail

sudo apt-get update
sudo apt-get install -y openjdk-25-jdk-headless maven fontconfig git

echo
echo "--- versions"
java -version 2>&1 | head -1
javac -version 2>&1 | head -1
mvn -version 2>&1 | head -1

version="$(java -version 2>&1 | head -1 | cut -d'"' -f2)"
major="${version%%.*}"
if [ "$major" -lt 25 ]; then
  echo
  echo "The default java is version $version. Select Java 25 with:"
  echo "  sudo update-alternatives --config java && sudo update-alternatives --config javac"
  exit 1
fi

# eqasim-france v1.5.0 reads `java -version` as exactly major.minor.patch and
# stops on builds that report anything else (Ubuntu's OpenJDK 25 can report
# four numbers, e.g. 25.0.1.1). Rather than patch eqasim, the simulation
# configs point its `java_binary` option at this small wrapper: it answers
# `-version` with the first three numbers and passes every other call straight
# to the real java.
REAL="$(readlink -f "$(command -v java)")"
mkdir -p "$HOME/eqasim-tools"
cat > "$HOME/eqasim-tools/java" <<WRAPPER
#!/usr/bin/env bash
REAL="$REAL"
if [ "\$#" -eq 1 ] && [ "\$1" = "-version" ]; then
  full="\$("\$REAL" -version 2>&1 | head -1 | cut -d'"' -f2)"
  IFS=. read -r major minor patch _ <<< "\${full%%[-+_]*}"
  echo "openjdk version \"\${major}.\${minor:-0}.\${patch:-0}\" (reported by \$REAL as \$full)" >&2
  exit 0
fi
exec "\$REAL" "\$@"
WRAPPER
chmod +x "$HOME/eqasim-tools/java"

echo
echo "java reports $version; eqasim will see $("$HOME/eqasim-tools/java" -version 2>&1 | cut -d'"' -f2)"
echo "Ready for the simulation step. Write the configs again now (configs/make_configs.py)."
