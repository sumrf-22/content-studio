# Content Studio

Local-first Instagram content pipeline with human approval gates.

Atlas -> approval -> Vera -> approval -> Kite -> approval -> Orin

## Run on Windows

```powershell
cd D:\Content-Studio
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe run.py
```

Open http://127.0.0.1:8080

Without an OpenRouter key the app runs in mock mode, so the dashboard can be tested safely.
