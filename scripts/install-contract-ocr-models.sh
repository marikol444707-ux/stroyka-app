#!/usr/bin/env bash
# Optional high-accuracy models, pinned upstream assets. No application secrets.
set -euo pipefail
model_dir=/usr/local/share/stroyka-tessdata-best
model_stage=$(mktemp -d)
trap 'rm -rf "$model_stage"' EXIT
model_commit=e12c65a915945e4c28e237a9b52bc4a8f39a0cec
for model_lang in rus eng; do
  curl -fsSL "https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/$model_commit/$model_lang.traineddata" -o "$model_stage/$model_lang.traineddata"
done
(cd "$model_stage" && sha256sum -c <<'HASHES'
b617eb6830ffabaaa795dd87ea7fd251adfe9cf0efe05eb9a2e8128b7728d6b6  rus.traineddata
8280aed0782fe27257a68ea10fe7ef324ca0f8d85bd2fd145d1c2b560bcb66ba  eng.traineddata
HASHES
)
curl -fsSL "https://raw.githubusercontent.com/tesseract-ocr/tessdata_best/$model_commit/LICENSE" -o "$model_stage/LICENSE"
install -d -m 755 "$model_dir"
install -m 644 "$model_stage/"* "$model_dir/"
