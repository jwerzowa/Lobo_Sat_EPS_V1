#!/usr/bin/env bash
# Download the datasheets listed in datasheets/README.md into datasheets/ (PDFs are gitignored).
# Usage: bash scripts/fetch_datasheets.sh
# Some vendors (analog.com, Fortune, Murata) block scripted downloads: get those by hand.
set -u
cd "$(dirname "$0")/../datasheets"
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 Chrome/120 Safari/537.36"

get() {
  if [ -s "$1" ] && file -b "$1" | grep -q PDF; then echo "have  $1"; return; fi
  curl -sL --http1.1 -A "$UA" --max-time 90 -o "$1.tmp" "$2"
  if file -b "$1.tmp" | grep -q PDF; then mv "$1.tmp" "$1"; echo "got   $1"
  else rm -f "$1.tmp"; echo "FAIL  $1  <- download by hand: $2"; fi
}

get S-8252.pdf    https://www.ablic.com/en/doc/datasheet/battery_protection/S8252_E.pdf
get BQ29209.pdf   https://www.ti.com/lit/ds/symlink/bq29209.pdf
get LMZM33602.pdf https://www.ti.com/lit/ds/symlink/lmzm33602.pdf
get TPS2553.pdf   https://www.ti.com/lit/ds/symlink/tps2553.pdf
get ADS1015.pdf   https://www.ti.com/lit/ds/symlink/ads1015.pdf
get INA228.pdf    https://www.ti.com/lit/ds/symlink/ina228.pdf
get LM393.pdf     https://www.ti.com/lit/ds/symlink/lm393.pdf
get AO3400A.pdf   https://www.aosmd.com/res/datasheets/AO3400A.pdf
get AO3401A.pdf   https://www.aosmd.com/res/datasheets/AO3401A.pdf
get SS-5GL.pdf    https://omronfs.omron.com/en_US/ecb/products/pdf/en-ss.pdf
get LT3652.pdf    https://www.analog.com/media/en/technical-documentation/data-sheets/3652fe.pdf
