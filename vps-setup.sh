#!/usr/bin/env bash
# Aruba VPS one-shot setup for betfair-research-backend.
# Generates a fresh client cert, prompts the user for Betfair credentials,
# builds the Docker image and starts the container.
#
# Run on the VPS as root:
#   curl -sL https://raw.githubusercontent.com/fnF4/betfair-research-backend/main/vps-setup.sh | bash
# or, after `git clone`:
#   bash vps-setup.sh

set -euo pipefail

REPO_DIR=/root/betfair-research-backend
CERT_DIR=/root/betfair-certs
ENV_FILE=$REPO_DIR/backend/.env
CONTAINER_NAME=betfair-bot
IMAGE_TAG=betfair-research-backend:latest

echo
echo "=================================================================="
echo " betfair-research-backend — VPS setup script"
echo "=================================================================="
echo

# ---------- 1. Repo --------------------------------------------------------
if [ ! -d "$REPO_DIR" ]; then
  echo "[1/6] Cloning repo..."
  cd /root
  git clone https://github.com/fnF4/betfair-research-backend.git
fi
cd "$REPO_DIR"
git pull --ff-only origin main || true
echo "[1/6] OK repo at $REPO_DIR"

# ---------- 2. Generate cert ----------------------------------------------
mkdir -p "$CERT_DIR"
if [ ! -f "$CERT_DIR/client-2048.crt" ]; then
  echo
  echo "[2/6] Generating SSL client certificate (2048 bit, valid 730 days)..."
  openssl req -newkey rsa:2048 -nodes \
    -keyout "$CERT_DIR/client-2048.key" \
    -x509 -days 730 \
    -out "$CERT_DIR/client-2048.crt" \
    -subj "/C=IT/ST=IT/L=Milano/O=Personal/OU=API/CN=betfair-bot-vps" 2>/dev/null
  chmod 600 "$CERT_DIR/client-2048.crt" "$CERT_DIR/client-2048.key"
fi
echo "[2/6] OK certs at $CERT_DIR"

# ---------- 3. Show cert so user can upload to Betfair --------------------
echo
echo "=================================================================="
echo " IMPORTANT — UPLOAD THIS CERT TO BETFAIR"
echo "=================================================================="
echo
echo " 1. Open https://myaccount.betfair.it/accountdetails/mysecurity?showAPI=1"
echo " 2. Remove your previous cert (if any) under 'Automated Betting Program Access'"
echo " 3. Click 'Upload Certificate' and paste the BLOCK BELOW"
echo " 4. Save"
echo
echo "------ BEGIN client-2048.crt -------------------------------------"
cat "$CERT_DIR/client-2048.crt"
echo "------ END client-2048.crt ---------------------------------------"
echo
read -r -p "Press ENTER once you have uploaded the cert on Betfair..."

# ---------- 4. Collect Betfair credentials --------------------------------
echo
echo "[4/6] Enter your Betfair credentials (input is hidden where appropriate)"
read -r -p "  BETFAIR_USERNAME (email): " BETFAIR_USERNAME
read -r -s -p "  BETFAIR_PASSWORD: " BETFAIR_PASSWORD; echo
read -r -p "  BETFAIR_APP_KEY (Delayed, 16 chars): " BETFAIR_APP_KEY
read -r -s -p "  ADMIN_SECRET (any random string for you): " ADMIN_SECRET; echo

# ---------- 5. Write .env -------------------------------------------------
mkdir -p "$REPO_DIR/backend"
cat > "$ENV_FILE" <<EOF
BETFAIR_LOCALE=italy
BETFAIR_USERNAME=$BETFAIR_USERNAME
BETFAIR_PASSWORD=$BETFAIR_PASSWORD
BETFAIR_APP_KEY=$BETFAIR_APP_KEY
BETFAIR_USE_CERTS=true
BETFAIR_CERT_PEM=$(awk 'BEGIN{ORS="\\n"}1' "$CERT_DIR/client-2048.crt")
BETFAIR_KEY_PEM=$(awk 'BEGIN{ORS="\\n"}1' "$CERT_DIR/client-2048.key")
BETFAIR_COMMISSION=0.05
BETFAIR_DATA_DIR=/data
BETFAIR_EVENT_TYPE_IDS=1,2
BETFAIR_HORIZON_HOURS=72
BETFAIR_TIER_1_LIMIT=30
BETFAIR_TIER_2_LIMIT=0
BETFAIR_MIN_TOTAL_MATCHED=1000
BETFAIR_CYCLE_SECONDS=45
BETFAIR_MIN_EDGE_NET=0.003
BETFAIR_SAFETY_MARGIN=1.5
BETFAIR_GHOST_MS=2000
BETFAIR_CAPITAL=10000
BETFAIR_PER_TRADE=500
BETFAIR_PAPER_MIN_EDGE=0.003
BETFAIR_PAPER_MIN_NOTIONAL=25
BETFAIR_MAX_HOLD_H=72
BETFAIR_ONLY_CATCHABLE=false
BETFAIR_EXECUTION_MODE=paper
BETFAIR_KILL_SWITCH=false
BETFAIR_ADMIN_SECRET=$ADMIN_SECRET
BETFAIR_CORS_ORIGINS=http://localhost:3000
BETFAIR_LOG_LEVEL=INFO
EOF
chmod 600 "$ENV_FILE"
echo "[5/6] OK env file written ($ENV_FILE)"

# ---------- 6. Build + run docker -----------------------------------------
echo
echo "[6/6] Building Docker image (first build ~3-5 minutes)..."
cd "$REPO_DIR"
docker build -t "$IMAGE_TAG" .

echo
echo "[6/6] Stopping any previous container..."
docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

echo "[6/6] Starting container..."
mkdir -p /data
docker run -d \
  --name "$CONTAINER_NAME" \
  --restart unless-stopped \
  --env-file "$ENV_FILE" \
  -p 80:8080 \
  -v /data:/data \
  "$IMAGE_TAG"

echo
echo "=================================================================="
echo " DONE!"
echo "=================================================================="
echo
sleep 3
docker ps --filter "name=$CONTAINER_NAME"
echo
echo "Logs (last 20 lines):"
docker logs --tail 20 "$CONTAINER_NAME" 2>&1 || true
echo
echo "Once running, hit:"
echo "  http://<this-vps-ip>/api/health"
echo "  http://<this-vps-ip>/api/status"
echo "  http://<this-vps-ip>/api/portfolio"
echo
echo "Tail logs live:    docker logs -f $CONTAINER_NAME"
echo "Restart container: docker restart $CONTAINER_NAME"
echo "Stop container:    docker stop $CONTAINER_NAME"
echo
