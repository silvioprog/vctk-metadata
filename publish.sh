#!/bin/sh

set -e

DIST_DIR="dist"
DATABASE_NAME="vctk-corpus"
BUCKET_NAME="vctk-corpus"

trap 'echo "Paused. Run again to continue."; exit 0' INT

echo "Checking database..."
d1_cache=".d1-cache"
if ! npx --yes wrangler d1 list | grep -q "$DATABASE_NAME"; then
    echo "Creating D1 database $DATABASE_NAME..."
    npx --yes wrangler d1 create $DATABASE_NAME
    echo "Waiting for database to be available..."
    while ! npx --yes wrangler d1 list | grep -q "$DATABASE_NAME"; do
        sleep 5
    done
    rm -f "$d1_cache"
fi
touch "$d1_cache"

if ! grep -q "^schema$" "$d1_cache"; then
    echo "Executing 01_schema.sql..."
    npx --yes wrangler d1 execute $DATABASE_NAME --remote --file="$DIST_DIR/01_schema.sql" --yes
    echo "schema" >> "$d1_cache"
fi

for file in "$DIST_DIR"/02_transcripts_*.sql; do
    if [ -f "$file" ]; then
        filename=$(basename "$file")
        if ! grep -q "^$filename$" "$d1_cache"; then
            echo "Executing $filename..."
            npx --yes wrangler d1 execute $DATABASE_NAME --remote --file="$file" --yes
            echo "$filename" >> "$d1_cache"
        fi
    fi
done

if ! grep -q "^indexes$" "$d1_cache"; then
    echo "Executing 03_indexes.sql..."
    npx --yes wrangler d1 execute $DATABASE_NAME --remote --file="$DIST_DIR/03_indexes.sql" --yes
    echo "indexes" >> "$d1_cache"
fi

echo "Checking bucket..."
if ! npx --yes wrangler r2 bucket list | grep -q "$BUCKET_NAME"; then
    npx --yes wrangler r2 bucket create $BUCKET_NAME
    echo "Waiting for bucket to be available..."
    while ! npx --yes wrangler r2 bucket list | grep -q "$BUCKET_NAME"; do
        sleep 5
    done
fi

r2_cache=".r2-cache"
touch "$r2_cache"

find "$DIST_DIR" -name "*.mp3" -type f | while read -r file; do
    relative_path="${file#"$DIST_DIR"/}"
    if ! grep -q "^$relative_path$" "$r2_cache"; then
        echo "Uploading $relative_path..."
        npx --yes wrangler r2 object put "$BUCKET_NAME/$relative_path" --remote --file="$file"
        echo "$relative_path" >> "$r2_cache"
    fi
done

echo "Done"
