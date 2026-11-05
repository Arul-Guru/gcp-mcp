# Lab 03 - IAM, Secret Manager, KMS
$SA="lab-runner"; $PROJ="floci-local"

Write-Host "`n== IAM: create a service account ==" -ForegroundColor Cyan
gcloud iam service-accounts create $SA --display-name="Lab Runner" --description="practice SA"
gcloud iam service-accounts list --format="table(email,displayName)"

Write-Host "`n== IAM: describe + grant a project role ==" -ForegroundColor Cyan
$EMAIL="$SA@$PROJ.iam.gserviceaccount.com"
gcloud iam service-accounts describe $EMAIL --format="yaml(email,displayName,uniqueId)"
gcloud projects add-iam-policy-binding $PROJ --member="serviceAccount:$EMAIL" --role="roles/pubsub.subscriber" --quiet

Write-Host "`n== IAM: read the policy back ==" -ForegroundColor Cyan
gcloud projects get-iam-policy $PROJ --format="yaml(bindings)"

Write-Host "`n== IAM: list predefined roles (first 5) ==" -ForegroundColor Cyan
gcloud iam roles list --limit=5 --format="table(name,title)"

Write-Host "`n== Secret Manager: create + add versions ==" -ForegroundColor Cyan
gcloud secrets create lab-db-password --replication-policy=automatic
"s3cr3t-v1" | gcloud secrets versions add lab-db-password --data-file=-
"s3cr3t-v2" | gcloud secrets versions add lab-db-password --data-file=-

Write-Host "`n== Secret Manager: list versions, access latest and v1 ==" -ForegroundColor Cyan
gcloud secrets versions list lab-db-password --format="table(name,state)"
Write-Host "latest ->" -NoNewline; gcloud secrets versions access latest --secret=lab-db-password
Write-Host "`nv1     ->" -NoNewline; gcloud secrets versions access 1 --secret=lab-db-password

Write-Host "`n`n== Secret Manager: disable a version ==" -ForegroundColor Cyan
gcloud secrets versions disable 1 --secret=lab-db-password
gcloud secrets versions list lab-db-password --format="table(name,state)"

Write-Host "`n== KMS: keyring + key + encrypt/decrypt round trip ==" -ForegroundColor Cyan
gcloud kms keyrings create lab-ring --location=global
gcloud kms keys create lab-key --location=global --keyring=lab-ring --purpose=encryption
gcloud kms keys list --location=global --keyring=lab-ring --format="table(name,purpose)"

$tmp = New-Item -ItemType Directory -Force -Path "$env:TEMP\floci-lab03"
"top secret payload" | Out-File "$tmp\plain.txt" -Encoding ascii -NoNewline
gcloud kms encrypt --location=global --keyring=lab-ring --key=lab-key --plaintext-file="$tmp\plain.txt" --ciphertext-file="$tmp\cipher.bin"
Write-Host "ciphertext bytes:" (Get-Item "$tmp\cipher.bin").Length
gcloud kms decrypt --location=global --keyring=lab-ring --key=lab-key --ciphertext-file="$tmp\cipher.bin" --plaintext-file="$tmp\back.txt"
Write-Host "decrypted ->" (Get-Content "$tmp\back.txt" -Raw)
