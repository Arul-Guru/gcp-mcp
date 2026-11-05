# Lab 01 - Cloud Storage (gcloud storage)
# Run:  .\labs\01-storage.ps1
$ErrorActionPreference = "Continue"
$B = "gs://lab-storage"

Write-Host "`n== 1. Create a bucket ==" -ForegroundColor Cyan
gcloud storage buckets create $B --location=us-central1

Write-Host "`n== 2. Upload objects ==" -ForegroundColor Cyan
$tmp = New-Item -ItemType Directory -Force -Path "$env:TEMP\floci-lab01"
"alpha"   | Out-File "$tmp\a.txt" -Encoding ascii -NoNewline
"bravo"   | Out-File "$tmp\b.txt" -Encoding ascii -NoNewline
"charlie" | Out-File "$tmp\c.log" -Encoding ascii -NoNewline
gcloud storage cp "$tmp\*" "$B/raw/"

Write-Host "`n== 3. List (flat, then recursive, then long) ==" -ForegroundColor Cyan
gcloud storage ls $B
gcloud storage ls --recursive $B
gcloud storage ls --long "$B/raw/"

Write-Host "`n== 4. Read an object without downloading ==" -ForegroundColor Cyan
gcloud storage cat "$B/raw/a.txt"

Write-Host "`n== 5. Object metadata ==" -ForegroundColor Cyan
gcloud storage objects describe "$B/raw/a.txt" --format="yaml(name,size,contentType,storageClass,md5Hash)"

Write-Host "`n== 6. Server-side copy and move ==" -ForegroundColor Cyan
gcloud storage cp "$B/raw/a.txt" "$B/archive/a-copy.txt"
gcloud storage mv "$B/raw/c.log" "$B/logs/c.log"
gcloud storage ls --recursive $B

Write-Host "`n== 7. Set custom metadata + content type ==" -ForegroundColor Cyan
gcloud storage objects update "$B/raw/b.txt" --content-type="text/plain" --custom-metadata=owner=arul,env=lab
gcloud storage objects describe "$B/raw/b.txt" --format="yaml(contentType,metadata)"

Write-Host "`n== 8. Bucket details ==" -ForegroundColor Cyan
gcloud storage buckets describe $B --format="yaml(name,location,storageClass,timeCreated)"

Write-Host "`n== 9. Delete one object, then the bucket recursively ==" -ForegroundColor Cyan
gcloud storage rm "$B/archive/a-copy.txt"
gcloud storage ls --recursive $B
