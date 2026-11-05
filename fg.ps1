# Convenience wrapper: runs a gcloud command against the local floci-gcp emulator.
#   .\fg.ps1 storage ls
$env:Path = "$env:LOCALAPPDATA\Google\Cloud SDK\google-cloud-sdk\bin;$env:Path"
. "$PSScriptRoot\floci-env.ps1" | Out-Null
& gcloud @args
