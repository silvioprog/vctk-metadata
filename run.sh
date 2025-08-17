#!/bin/sh

set -e

DIST_DIR="dist"
TMP_DIR="tmp"

rm -rf "$DIST_DIR"

mkdir -p "$DIST_DIR"
mkdir -p "$TMP_DIR"

file="VCTK-Corpus-0.92.zip"

echo "Downloading resources..."
base_url="https://datashare.ed.ac.uk/bitstream/handle/10283/3443"
wget --no-verbose --continue --show-progress "$base_url/$file" -P "$TMP_DIR"

echo "Extracting resources..."
unzip -qn "$TMP_DIR/$file" -d "$TMP_DIR"

echo "Preparing environment..."
python3 -m venv venv
venv/bin/pip install --upgrade pip --quiet
venv/bin/pip install -r requirements.txt --quiet

echo "Generating files..."
venv/bin/python generator.py "$DIST_DIR" "$TMP_DIR"

echo "Done"
