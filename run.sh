#!/bin/bash
SRC="/home/thune/source/privat/content_generation_studio"
DST="/mnt/c/projects/studio"

# Collect files to sync (skip .pyc, __pycache__, .git, .venv)
mapfile -t FILES < <(find "$SRC" -type f \
    ! -name "*.pyc" \
    ! -path "*/__pycache__/*" \
    ! -path "*/.git/*" \
    ! -path "*/.venv*")

TOTAL=${#FILES[@]}
COUNT=0
COPIED=0

echo "Syncing $TOTAL files..."

for FILE in "${FILES[@]}"; do
    COUNT=$((COUNT + 1))
    REL="${FILE#$SRC/}"
    DEST="$DST/$REL"

    # Only copy if changed or new
    if [ ! -f "$DEST" ] || [ "$FILE" -nt "$DEST" ]; then
        mkdir -p "$(dirname "$DEST")"
        cp "$FILE" "$DEST"
        COPIED=$((COPIED + 1))
    fi

    PCT=$((COUNT * 100 / TOTAL))
    # Progress bar (20 chars wide)
    FILLED=$((PCT / 5))
    BAR=$(printf '%0.s█' $(seq 1 $FILLED))
    EMPTY=$(printf '%0.s░' $(seq 1 $((20 - FILLED))))
    printf "\r  [%s%s] %3d%%  (%d/%d)" "$BAR" "$EMPTY" "$PCT" "$COUNT" "$TOTAL"
done

echo ""
echo "  $COPIED file(s) updated."
echo ""
echo "Starting app..."
powershell.exe -Command "& 'C:\\projects\\studio\\.venv-win\\Scripts\\python.exe' 'C:\\projects\\studio\\main.py' 2>&1"
echo "App closed."
