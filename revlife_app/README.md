# Rev Life 1035 Exchange Platform

## Project Structure
```
revlife_app/
├── server.py          # Flask backend — handles API proxy and serves the app
├── requirements.txt   # Python dependencies
├── Procfile           # For Railway/Render deployment
├── static/
│   └── index.html     # Full frontend app
```

## Environment Variables Required
- `ANTHROPIC_API_KEY` — your Anthropic API key (set in hosting platform dashboard)

## Local Development
```bash
pip install -r requirements.txt
ANTHROPIC_API_KEY=your_key_here python server.py
```
Then open http://localhost:5001

## Deployment (Railway — recommended)
1. Push this folder to a GitHub repo
2. Go to railway.app → New Project → Deploy from GitHub
3. Set environment variable: ANTHROPIC_API_KEY = your key
4. Railway auto-detects Procfile and deploys
5. Get your public URL from the Railway dashboard

## Deployment (Render)
1. Push to GitHub
2. Go to render.com → New Web Service → connect repo
3. Build command: `pip install -r requirements.txt`
4. Start command: `gunicorn server:app`
5. Set ANTHROPIC_API_KEY in environment variables

## Login Credentials
- FMO login: lifeteam@revolutionmo.com / fmo2026
- Agent invite code: IUL2026

## Notes
- All case data is stored in browser localStorage (per device)
- For shared persistent storage across devices, a database upgrade is needed (Phase 3)
