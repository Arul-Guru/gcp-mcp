# Dot-source this to point GCP SDKs and gcloud at the local floci-gcp emulator:
#   . .\floci-env.ps1
# Affects only the current PowerShell session. Your real gcloud config is untouched.

# Ensure Google Cloud SDK is in PATH if installed in standard local AppData
$gcloudBin = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin"
if ((Test-Path $gcloudBin) -and ($env:Path -split ';' -notcontains $gcloudBin)) {
    $env:Path = "$gcloudBin;$env:Path"
}

$FlociEndpoint = "http://localhost:4588/"

# --- Client SDK emulator hosts (google-cloud-* libraries) ---
$env:PUBSUB_EMULATOR_HOST         = "localhost:4588"
$env:FIRESTORE_EMULATOR_HOST      = "localhost:4588"
$env:DATASTORE_EMULATOR_HOST      = "localhost:4588"
$env:SECRET_MANAGER_EMULATOR_HOST = "localhost:4588"
$env:STORAGE_EMULATOR_HOST        = "http://localhost:4588"   # this one takes the scheme

# --- gcloud CLI (ignores the *_EMULATOR_HOST vars; needs its own overrides) ---
$env:CLOUDSDK_CORE_PROJECT       = "floci-local"
$env:CLOUDSDK_AUTH_ACCESS_TOKEN  = "floci-local-token"   # any token works locally
$env:CLOUDSDK_CORE_DISABLE_PROMPTS = "1"

foreach ($svc in @(
    "PUBSUB","STORAGE","SECRETMANAGER","FIRESTORE","DATASTORE","BIGQUERY",
    "RUN","CLOUDTASKS","CLOUDSCHEDULER","CLOUDKMS","COMPUTE","LOGGING",
    "MONITORING","IAM","CLOUDRESOURCEMANAGER","SQLADMIN","EVENTARC",
    "CLOUDFUNCTIONS","CONTAINER","SERVICEUSAGE","CLOUDBILLING","MANAGEDKAFKA"
)) {
    Set-Item -Path "env:CLOUDSDK_API_ENDPOINT_OVERRIDES_$svc" -Value $FlociEndpoint
}

Write-Host "floci-gcp environment active -> $FlociEndpoint (project: floci-local)" -ForegroundColor Green
