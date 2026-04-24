# Betfair Research Backend

Research-only, paper-trading-only backend that scans Betfair Exchange for
**Category-1 arbitrage** (crossed back/lay on the same selection) and
simulates the hedged trade. Identical architecture to the Polymarket
research backend: FastAPI + SQLite + autonomous scheduler + Next.js
dashboard.

**Compliance:** no orders are ever placed. The live-execution module is
intentionally not shipped in this repo. `BETFAIR_EXECUTION_MODE` accepts
only `paper` or `disabled_live`.

## Project layout

```
betfair-research-backend/
├── backend/          FastAPI service (Render)
│   ├── api.py            endpoints + in-process scheduler thread
│   ├── config.py         env-driven config + snapshot
│   ├── storage.py        SQLite schema + migrations
│   ├── killswitch.py     runtime kill-switch (env or DB)
│   ├── health.py         /api/health status computation
│   ├── betfair_client.py session-lifetime wrapper on betfairlightweight
│   ├── arbitrage.py      Category-1 detection math
│   ├── collector.py      one scan cycle (catalogue → book → opps → paper)
│   ├── paper_trading.py  open/update/close virtual positions
│   ├── logger_setup.py   logging config
│   └── requirements.txt
├── frontend/         Next.js dashboard (Vercel)
│   ├── src/app          Dashboard, Opportunities, Setup, Compliance
│   ├── src/components   same widgets as the Polymarket frontend
│   └── package.json
├── infra/
│   └── render.yaml   Render Blueprint (backend Starter plan)
├── shared/
│   └── types.ts      documentative API contract
├── .env.example      full list of environment variables
└── README.md         this file
```

## Cost

- **Render Starter** for the backend: **$7/mo** (always-on, 1 GB persistent disk for SQLite)
- **Vercel Hobby** for the frontend: **$0**
- **Betfair "Delayed" application key**: **free** (sufficient for research)
- **Live application key** (NOT required for research): 299£ one-time

No wallet, no gas, no third-party data feed costs.

## Setup step-by-step

### 1. Betfair account

1. Open a verified account at <https://www.betfair.it>. Upload ID document.
2. Go to <https://developer.betfair.com/> → "Get API Access".
3. Create a **"Delayed" application key** (free). Note it down.
4. (Optional, recommended for 24/7) Upload a self-signed client SSL
   certificate and set `BETFAIR_USE_CERTS=true` + the cert/key paths.

### 2. GitHub repo

1. Create a new PRIVATE GitHub repo (e.g. `betfair-research-backend`).
2. Push this project to it:
   ```bash
   git init
   git add .
   git commit -m "initial scaffold"
   git branch -M main
   git remote add origin git@github.com:<you>/betfair-research-backend.git
   git push -u origin main
   ```

### 3. Render backend deploy

1. Render Dashboard → **New** → **Blueprint** → pick the repo.
2. Render picks up `infra/render.yaml` automatically.
3. Fill the **non-synced** env vars in the Dashboard (these are not
   committed): `BETFAIR_USERNAME`, `BETFAIR_PASSWORD`, `BETFAIR_APP_KEY`,
   `BETFAIR_CORS_ORIGINS` (the Vercel URL once you have it).
4. **Apply**. First deploy ≈ 3-5 minutes.
5. Verify: `curl https://<your-service>.onrender.com/api/health`

### 4. Vercel frontend deploy

1. Vercel Dashboard → **New Project** → pick the same repo.
2. Root directory: `frontend/`
3. Framework: Next.js (auto-detected)
4. Env var: `NEXT_PUBLIC_API_URL` = your Render service URL
5. **Deploy**. ≈ 2 minutes.
6. Back to Render, set `BETFAIR_CORS_ORIGINS` to include the Vercel URL,
   redeploy.

### 5. First scan

Lo scheduler interno parte automaticamente 15 secondi dopo il boot del
backend. Controlla `/api/health` e `/api/portfolio` dopo 1-2 minuti.

Per forzare subito un ciclo di scan:
```bash
curl -X POST https://<backend>.onrender.com/api/admin/scan \
     -H "X-Admin-Secret: <BETFAIR_ADMIN_SECRET>"
```

## Local development

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # fill in values
export $(cat .env | xargs)
uvicorn api:app --reload --port 8000

# Frontend (other shell)
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

Open <http://localhost:3000>.

## Admin endpoints

All require the `X-Admin-Secret` header equal to `BETFAIR_ADMIN_SECRET`.

- `POST /api/admin/scan` — trigger one scan cycle immediately
- `POST /api/admin/kill`  (body `{"reason": "..."}`) — stop the scanner
- `POST /api/admin/unkill` — resume
- `POST /api/admin/reset-paper-trading?confirm=YES_WIPE_ALL_PAPER_DATA` — wipe paper state

## Disclaimer

Questa piattaforma è strumento di ricerca, simulazione ed educazione. Non
è consulenza finanziaria né invito a scommettere. L'utente è l'unico
responsabile di ogni uso di questi dati, incluso ma non limitato a
qualunque eventuale applicazione su capitale reale.
