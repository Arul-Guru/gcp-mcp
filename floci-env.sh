# Source this to point GCP SDKs and gcloud at the local floci-gcp emulator:
#   source ./floci-env.sh
# Affects only the current shell. Your real gcloud config is untouched.

# Warn if executed directly instead of sourced
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    echo "ERROR: floci-env.sh was executed directly in a subshell." >&2
    echo "To set environment variables in your current shell, run:" >&2
    echo "    source ./floci-env.sh" >&2
    echo "or" >&2
    echo "    . ./floci-env.sh" >&2
    exit 1
fi

# Ensure Google Cloud SDK is in PATH (handling Windows/Git Bash POSIX paths)
if command -v cygpath >/dev/null 2>&1 && [ -n "$LOCALAPPDATA" ]; then
    GCLOUD_BIN="$(cygpath -u "$LOCALAPPDATA")/Google/Cloud SDK/google-cloud-sdk/bin"
elif [ -n "$LOCALAPPDATA" ] && [ -d "$LOCALAPPDATA/Google/Cloud SDK/google-cloud-sdk/bin" ]; then
    GCLOUD_BIN="$LOCALAPPDATA/Google/Cloud SDK/google-cloud-sdk/bin"
else
    GCLOUD_BIN="$HOME/AppData/Local/Google/Cloud SDK/google-cloud-sdk/bin"
fi

if [ -d "$GCLOUD_BIN" ] && [[ ":$PATH:" != *":$GCLOUD_BIN:"* ]]; then
    export PATH="$GCLOUD_BIN:$PATH"
fi

FLOCI_ENDPOINT="http://localhost:4588/"

# --- Client SDK emulator hosts (google-cloud-* libraries) ---
export PUBSUB_EMULATOR_HOST="localhost:4588"
export FIRESTORE_EMULATOR_HOST="localhost:4588"
export DATASTORE_EMULATOR_HOST="localhost:4588"
export SECRET_MANAGER_EMULATOR_HOST="localhost:4588"
export STORAGE_EMULATOR_HOST="http://localhost:4588"   # this one takes the scheme

# --- gcloud CLI (ignores the *_EMULATOR_HOST vars; needs its own overrides) ---
export CLOUDSDK_CORE_PROJECT="floci-local"
export CLOUDSDK_AUTH_ACCESS_TOKEN="floci-local-token"   # any token works locally
export CLOUDSDK_CORE_DISABLE_PROMPTS="1"

for svc in PUBSUB STORAGE SECRETMANAGER FIRESTORE DATASTORE BIGQUERY \
           RUN CLOUDTASKS CLOUDSCHEDULER CLOUDKMS COMPUTE LOGGING \
           MONITORING IAM CLOUDRESOURCEMANAGER SQLADMIN EVENTARC \
           CLOUDFUNCTIONS CONTAINER SERVICEUSAGE CLOUDBILLING MANAGEDKAFKA; do
    export "CLOUDSDK_API_ENDPOINT_OVERRIDES_${svc}=${FLOCI_ENDPOINT}"
done

echo "floci-gcp environment active -> ${FLOCI_ENDPOINT} (project: floci-local)"
