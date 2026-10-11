#!/usr/bin/env bash
set -euo pipefail

project_directory="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
environment_file="$project_directory/.env"
if [[ ! -f "$environment_file" ]]; then
    printf 'Missing .env; configure it using .env.example first.\n' >&2
    exit 1
fi
set -a
source "$environment_file"
set +a

subscription="${AZURE_SUBSCRIPTION_ID:?Set AZURE_SUBSCRIPTION_ID in .env}"
account="${AZURE_STORAGE_ACCOUNT:?Set AZURE_STORAGE_ACCOUNT in .env}"
container="${AZURE_STORAGE_CONTAINER:?Set AZURE_STORAGE_CONTAINER in .env}"

for dependency in az curl jq shasum; do
    command -v "$dependency" >/dev/null || {
        printf 'Missing dependency: %s\n' "$dependency" >&2
        exit 1
    }
done

az storage container show \
    --subscription "$subscription" \
    --account-name "$account" \
    --name "$container" \
    --auth-mode login \
    --only-show-errors --output none

temporary_directory="$(mktemp -d)"
trap 'rm -rf "$temporary_directory"' EXIT
upload_directory="$temporary_directory/upload"
mkdir -p "$upload_directory"
snapshot="$(date -u +%Y%m%dT%H%M%SZ)"
prefix="raw/project-gutenberg/$snapshot"
retrieved_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

while IFS='|' read -r ebook_id slug expected_title; do
    source_url="https://www.gutenberg.org/cache/epub/$ebook_id/pg$ebook_id.txt"
    filename="$slug.txt"
    destination="$upload_directory/$filename"
    printf 'Downloading %s\n' "$expected_title"
    curl --fail --silent --show-error --location --retry 2 \
        --output "$destination" "$source_url"
    grep -Fqi "Title: $expected_title" "$destination"
    grep -Fq 'Author: William Shakespeare' "$destination"
    grep -Fq 'START OF THE PROJECT GUTENBERG' "$destination"
    checksum="$(shasum -a 256 "$destination" | awk '{print $1}')"
    byte_count="$(wc -c < "$destination")"
    actual_title="$(sed -n 's/^Title: //p' "$destination" | head -n 1 | tr -d '\r')"
    jq -n \
        --arg id "gutenberg-$ebook_id" \
        --arg title "$actual_title" \
        --arg source_url "$source_url" \
        --arg source_page "https://www.gutenberg.org/ebooks/$ebook_id" \
        --arg blob_name "$prefix/$filename" \
        --arg sha256 "$checksum" \
        --argjson bytes "$byte_count" \
        '{id: $id, title: $title, author: "William Shakespeare", source_url: $source_url,
          source_page: $source_page, blob_name: $blob_name, sha256: $sha256, bytes: $bytes,
          format: "text/plain", original_notices_preserved: true}' \
        >> "$temporary_directory/documents.jsonl"
done <<'BOOKS'
1524|hamlet|Hamlet
1533|macbeth|Macbeth
1513|romeo-and-juliet|Romeo and Juliet
1531|othello|Othello
1532|king-lear|King Lear
1514|a-midsummer-nights-dream|A Midsummer Night
1515|the-merchant-of-venice|The Merchant of Venice
1522|julius-caesar|Julius Caesar
1540|the-tempest|The Tempest
1526|twelfth-night|Twelfth Night
BOOKS

jq --slurp \
    --arg snapshot "$snapshot" \
    --arg retrieved_at "$retrieved_at" \
    '{corpus: "shakespeare", snapshot: $snapshot, retrieved_at: $retrieved_at,
      rights_note: "Original Shakespeare works are public domain; Project Gutenberg notices are preserved. Check edition terms and applicable local law before redistribution.",
      documents: .}' \
    "$temporary_directory/documents.jsonl" > "$upload_directory/manifest.json"
jq --exit-status '.documents | length == 10' "$upload_directory/manifest.json" >/dev/null

az storage blob upload-batch \
    --subscription "$subscription" \
    --account-name "$account" \
    --destination "$container" \
    --destination-path "$prefix" \
    --source "$upload_directory" \
    --auth-mode login \
    --overwrite false \
    --only-show-errors --output none

uploaded_count="$(az storage blob list \
    --subscription "$subscription" \
    --account-name "$account" \
    --container-name "$container" \
    --prefix "$prefix/" \
    --auth-mode login \
    --query 'length(@)' \
    --only-show-errors --output tsv)"
if [[ "$uploaded_count" != "11" ]]; then
    printf 'Expected 10 texts and one manifest; found %s blobs.\n' "$uploaded_count" >&2
    exit 1
fi

az storage blob download \
    --subscription "$subscription" \
    --account-name "$account" \
    --container-name "$container" \
    --name "$prefix/hamlet.txt" \
    --file "$temporary_directory/hamlet-roundtrip.txt" \
    --auth-mode login \
    --only-show-errors --output none
cmp "$upload_directory/hamlet.txt" "$temporary_directory/hamlet-roundtrip.txt"

mkdir -p "$project_directory/.artifacts"
jq -n \
    --arg prefix "$prefix" \
    --arg manifest_blob "$prefix/manifest.json" \
    --arg snapshot "$snapshot" \
    '{prefix: $prefix, manifest_blob: $manifest_blob, snapshot: $snapshot, document_count: 10}' \
    > "$project_directory/.artifacts/corpus-upload.json"

printf '\nVerified 10 texts and one manifest; Hamlet round-trip matches.\n'
printf 'Corpus: https://%s.blob.core.windows.net/%s/%s/\n' "$account" "$container" "$prefix"
printf 'Manifest: %s/manifest.json\n' "$prefix"