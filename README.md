# Sentiment Analysis Dashboard

FastAPI (Python) backend wrapping a pre-trained HuggingFace sentiment
checkpoint (text + emoji), with a dark chat-style frontend.

```
backend/    FastAPI, SQLAlchemy, JWT-cookie auth, model service, tests, Dockerfile
frontend/   Static HTML/CSS/JS (no build step) + vercel.json
model/      Put your HuggingFace checkpoint files here
```

## Run locally

1. Put `config.json`, `model.safetensors`, `tokenizer_config.json`,
   `tokenizer.json`, `training_args.bin` in `model/`. Labels come from the
   checkpoint's own `id2label`; nothing is hardcoded.
2. Backend:
   ```bash
   cd backend
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env        # set SECRET_KEY; MODEL_PATH defaults to ../model
   uvicorn app.main:app --reload --port 8000
   ```
   `curl localhost:8000/api/health` -> `"model_loaded": true` once loaded.
   Photo/video input needs the **Tesseract** OCR engine on the machine
   (`sudo apt install tesseract-ocr` / `brew install tesseract`; the Dockerfile already installs it).
   Tests: `pytest` (uses a fake model; no weights needed).

   > **Upgrading from the previous version?** Sign-in now uses **email** and chats
   > have a `chat_id`, so the database schema changed. For local dev delete
   > `backend/sentiment_app.db` once; it is recreated on start.
3. Frontend: `cd frontend && python -m http.server 5500`, open
   `http://localhost:5500` (or `http://127.0.0.1:5500` — both work out of
   the box against `FRONTEND_ORIGINS` in `.env.example`).

## What you edit yourself — `frontend/js/config.js`

| Setting | What it does |
|---|---|
| `LINKS.research` | Document opened by **Research** (default: placeholder `docs/research-paper.html`; point it at your PDF) |
| `LINKS.futureScope` | Page opened by **Future Scope** (`future-scope.html`, plain HTML — edit freely) |
| `LINKS.minProf` | Your portfolio link |
| `LINKS.workDirectory` | Link for **WorkDirectory** (empty = shows "link not set yet") |
| `LANDING_MEDIA.left / right` | Video paths for the two 200×200 squares (put files in `frontend/media/`) |
| `MEDIA_LIMITS` | Upload limits shown to the user — keep equal to `MAX_IMAGE_BYTES` / `MAX_VIDEO_BYTES` / `MAX_VIDEO_SECONDS` in `backend/.env` |

The **MCP** item in the sidebar opens `frontend/mcp.html`, an intentionally empty page (`#mcp-root`) for your MCP code.

## How the new pieces work

- **New chat on every visit.** The browser starts a new `chat_id` each time the dashboard opens. Everything is
  still stored; older chats are listed under *Recent chats* in the sidebar.
- **Photo / short video (+ button).** `POST /api/predict/media` → extract text (Tesseract OCR; for video, 6 frames
  sampled across the clip) → sentiment model → result + pie chart. Only the extracted text is stored, never the file.
  Limits: image 5 MB, video 20 MB / 30 s. Speech in videos is *not* transcribed.
- **Share.** Creates an unguessable read-only link (`shared.html?t=…`) to one chat. "Delete my data" also revokes links.
- **Download.** Current chat as a `.md` file, generated in the browser.
- **Sign-in.** Email + password; the email format is checked live in the browser and again on the server
  (format only — no confirmation mail is sent). Sign-up offers a generated password or your own., backend elsewhere

**The backend cannot realistically run on Vercel.** Serverless functions have
a bundle-size cap and no persistent disk; torch + transformers + your model
weights will very likely exceed it (check Vercel's current limits), the model
would reload on cold starts, and SQLite would not persist. Split it:

1. **Backend** on any container host (Render, Railway, Fly.io, AWS Fargate...)
   using `backend/Dockerfile`. Provide the checkpoint at `/model` (bake it in
   or mount a volume). Environment variables:
   ```
   ENV=production            # app refuses to start with the default SECRET_KEY
   SECRET_KEY=<long random>
   COOKIE_SECURE=true
   FRONTEND_ORIGINS=https://<your-app>.vercel.app
   DATABASE_URL=postgresql+psycopg2://...   # also: pip install psycopg2-binary
   MODEL_PATH=/model
   ```
2. **Frontend** on Vercel: edit `frontend/vercel.json`, replacing
   `YOUR-BACKEND-HOST` with your backend's hostname, then:
   ```bash
   cd frontend
   npx vercel --prod
   ```
   (or import the repo in Vercel with **Root Directory = `frontend`**,
   Framework Preset = Other).

The `/api/*` rewrite makes the browser talk to Vercel's own origin, so the
HTTP-only session cookie stays first-party. No cross-site cookie or CORS
tuning is needed.

## Notes

- "Delete my data" removes a user's submissions + results only; the account stays.
- `/api/mcp` is an intentional empty stub (501); the sidebar's MCP item opens the empty `mcp.html` page.
- Text is sanitized (control characters stripped) before storage and rendered
  with `textContent`, so stored HTML is never executed.
