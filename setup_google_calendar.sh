#!/bin/bash
# Setup Google Cloud service account for Calendar API access
# Run this once, then do the ONE manual step in Admin Console.

set -e

PROJECT_ID="slashr-calendar-api"
SA_NAME="calendar-reader"
SA_EMAIL="${SA_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
KEY_FILE="$(dirname "$0")/google_sa_key.json"

echo "=== Google Calendar API Setup ==="
echo ""

# 1. Check gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "ERROR: gcloud CLI not installed."
    echo "Install: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# 2. Login if needed
echo "[1/5] Checking gcloud auth..."
gcloud auth list --filter=status:ACTIVE --format="value(account)" | head -1 || {
    echo "  Logging in..."
    gcloud auth login
}

# 3. Create project (or use existing)
echo ""
echo "[2/5] Creating project ${PROJECT_ID}..."
if gcloud projects describe "$PROJECT_ID" &> /dev/null; then
    echo "  Project already exists."
else
    gcloud projects create "$PROJECT_ID" --name="SLASHR Calendar API"
    echo "  Project created."
fi
gcloud config set project "$PROJECT_ID"

# 4. Enable Calendar API
echo ""
echo "[3/5] Enabling Google Calendar API..."
gcloud services enable calendar-json.googleapis.com

# 5. Create service account
echo ""
echo "[4/5] Creating service account..."
if gcloud iam service-accounts describe "$SA_EMAIL" &> /dev/null 2>&1; then
    echo "  Service account already exists."
else
    gcloud iam service-accounts create "$SA_NAME" \
        --display-name="Calendar Reader for Dashboard"
    echo "  Service account created."
fi

# 6. Download key
echo ""
echo "[5/5] Generating key file..."
if [ -f "$KEY_FILE" ]; then
    echo "  Key file already exists at $KEY_FILE"
else
    gcloud iam service-accounts keys create "$KEY_FILE" \
        --iam-account="$SA_EMAIL"
    echo "  Key saved to $KEY_FILE"
fi

# Get the client ID for the manual step
echo ""
echo "============================================"
echo "  AUTOMATED SETUP COMPLETE"
echo "============================================"
echo ""
echo "Service account: $SA_EMAIL"

# Extract client_id from key file
CLIENT_ID=$(python3 -c "import json; print(json.load(open('$KEY_FILE'))['client_id'])")
echo "Client ID:       $CLIENT_ID"
echo ""
echo "============================================"
echo "  ONE MANUAL STEP REQUIRED"
echo "============================================"
echo ""
echo "Go to: https://admin.google.com/ac/owl/domainwidedelegation"
echo ""
echo "  1. Click 'Add new'"
echo "  2. Client ID: $CLIENT_ID"
echo "  3. Scopes:    https://www.googleapis.com/auth/calendar.readonly"
echo "  4. Click 'Authorize'"
echo ""
echo "Then run: python3 fetch_google_calendar.py"
echo ""
