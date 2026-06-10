# Deploy in ~1 hour (no custom domain required)

You get a **free public URL** without buying a domain:

| Host | Example URL |
|------|-------------|
| **Render** (recommended) | `https://thesis-tool.onrender.com` |
| Vercel | `https://your-project.vercel.app` |

A custom domain (e.g. `thesis.yoursite.com`) is **optional** and can be added later in the host dashboard (~$10–15/year if you buy one).

---

## Important: Vercel vs this app

You mentioned **Vercel**. It works for a **demo**, but this project is **Python FastAPI**, not Next.js:

| Issue | Vercel Hobby | Render (free web service) |
|-------|----------------|---------------------------|
| Python FastAPI | Serverless, awkward for static + API | Native `uvicorn` |
| Request timeout | **10 seconds** | No 10s cap on web services |
| EDGAR live fetch | **Fails** (60–90s) | OK for background jobs later |
| Cold start | Every request possible | ~30s wake after idle |

**For a 1-hour launch, use Render.** Use Vercel only if you already insist on it — with **cached data only** (we ship MSFT + AAPL JSON in the repo).

Production mode: `ALLOW_LIVE_FETCH=false` → users read **cached** snapshots; no SEC/FMP call per visit.

---

## Path A — Render (~20 minutes) ✅ recommended

### 1. Push code to GitHub (~5 min)

In PowerShell, from the project folder:

```powershell
cd C:\Users\HOME\value-investing-analyzer
git init
git add .
git commit -m "Prepare public deploy with cached tickers"
```

Create a repo on GitHub (empty, no README), then:

```powershell
git remote add origin https://github.com/YOUR_USER/value-investing-analyzer.git
git branch -M main
git push -u origin main
```

Do **not** commit `backend/.env` (already in `.gitignore`).

### 2. Create Render service (~10 min)

1. Go to [render.com](https://render.com) → sign up (GitHub login).
2. **New → Blueprint** (or **Web Service** if Blueprint is unavailable).
3. Connect your GitHub repo.
4. Render reads `render.yaml` at repo root:
   - Root directory: `backend`
   - Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`
5. **Environment variables** (Render dashboard → Environment):

   | Key | Value |
   |-----|--------|
   | `SEC_USER_AGENT` | `ThesisTool your.email@example.com` |
   | `ALLOW_LIVE_FETCH` | `false` |
   | `FMP_API_KEY` | optional — not needed for cached MSFT/AAPL |

6. Click **Deploy**. First build ~3–5 min.

Your URL: `https://thesis-tool.onrender.com` (or the name Render assigns).

### 3. Test

- `https://YOUR-URL.onrender.com/` → MSFT thesis
- `https://YOUR-URL.onrender.com/?ticker=AAPL&source=edgar` → Apple (cached EDGAR)
- `https://YOUR-URL.onrender.com/api/health` → lists `cached_tickers`

**Note:** Free Render sleeps after ~15 min idle; first visit may take **30–60 s** to wake.

---

## Path B — Vercel (~15 min, limitations)

Only if you must use Vercel:

1. Install Vercel CLI: `npm i -g vercel`
2. From project root: `vercel` → follow prompts.
3. Set env vars in Vercel dashboard:
   - `ALLOW_LIVE_FETCH=false`
   - `SEC_USER_AGENT=ThesisTool your.email@example.com`
4. `vercel.json` is already in the repo.

**Limits:** 10s timeout on Hobby → live EDGAR/FMP will fail; cached MSFT/AAPL only. Upgrade to Pro (60s) still may fail on EDGAR.

---

## Custom domain (optional, later)

Neither Render nor Vercel **requires** a purchased domain.

When ready:

1. Buy a domain (Namecheap, Cloudflare, Google Domains, ~$10–15/year).
2. In Render/Vercel → **Settings → Custom Domains** → add domain → follow DNS instructions (usually one CNAME record).

---

## What is cached at launch

| Ticker | File | URL |
|--------|------|-----|
| MSFT | `msft_1data.json` (Excel reference) | `/` |
| AAPL | `aapl_edgar_1data.json` | `/?ticker=AAPL&source=edgar` |

To add tickers before launch: run locally `fetch_edgar_ticker.py TICKER --save`, commit the new JSON under `backend/data/`, redeploy.

---

## Checklist (1 hour)

- [ ] Git push to GitHub
- [ ] Render web service connected
- [ ] `SEC_USER_AGENT` set in Render env
- [ ] `ALLOW_LIVE_FETCH=false`
- [ ] Open public URL — MSFT loads
- [ ] Open `?ticker=AAPL&source=edgar` — Apple loads
- [ ] Share link (no domain purchase needed)

Optional later: custom domain, paid Render (no sleep), background refresh pipeline for new 10-K filings.
