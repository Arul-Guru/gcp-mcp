#!/usr/bin/env bash
# Lab 06 - the services gcloud can't reach, via plain REST.
# Run from git-bash:  bash labs/06-rest.sh
E="http://localhost:4588"
P="floci-local"

echo "== Cloud Run: list services =="
curl -s "$E/v2/projects/$P/locations/us-central1/services"; echo

echo "== Cloud Run: create a service =="
curl -s -X POST "$E/v2/projects/$P/locations/us-central1/services?serviceId=lab-svc" \
  -H "Content-Type: application/json" \
  -d '{"template":{"containers":[{"image":"nginx:alpine"}]}}'; echo

echo "== Cloud Run: list again =="
curl -s "$E/v2/projects/$P/locations/us-central1/services" | head -c 600; echo

echo "== BigQuery: list datasets =="
curl -s "$E/bigquery/v2/projects/$P/datasets"; echo

echo "== BigQuery: create a dataset =="
curl -s -X POST "$E/bigquery/v2/projects/$P/datasets" \
  -H "Content-Type: application/json" \
  -d '{"datasetReference":{"datasetId":"lab_ds","projectId":"'"$P"'"}}' | head -c 400; echo

echo "== BigQuery: create a table =="
curl -s -X POST "$E/bigquery/v2/projects/$P/datasets/lab_ds/tables" \
  -H "Content-Type: application/json" \
  -d '{"tableReference":{"projectId":"'"$P"'","datasetId":"lab_ds","tableId":"events"},
       "schema":{"fields":[{"name":"id","type":"INTEGER"},{"name":"name","type":"STRING"}]}}' | head -c 400; echo

echo "== BigQuery: list tables =="
curl -s "$E/bigquery/v2/projects/$P/datasets/lab_ds/tables" | head -c 400; echo
