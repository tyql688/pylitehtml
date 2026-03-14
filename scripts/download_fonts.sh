#!/usr/bin/env bash
set -e
mkdir -p fonts

curl -L "https://github.com/dejavu-fonts/dejavu-fonts/releases/download/version_2_37/dejavu-fonts-ttf-2.37.tar.bz2" \
  -o /tmp/dejavu.tar.bz2
tar -xjf /tmp/dejavu.tar.bz2 -C /tmp
cp /tmp/dejavu-fonts-ttf-2.37/ttf/DejaVuSans.ttf fonts/

curl -L "https://github.com/google/fonts/raw/main/ofl/notosans/NotoSans-Regular.ttf" \
  -o fonts/NotoSans-Regular.ttf

curl -L "https://github.com/google/fonts/raw/main/ofl/notosanssc/NotoSansSC-Regular.otf" \
  -o fonts/NotoSansSC-Regular.otf

echo "Done: $(ls -lh fonts/)"
