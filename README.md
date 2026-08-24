## HR Screening Tool

This application provides evidence-grounded candidate recommendations. It does not make hiring decisions.

### Run locally

1. Copy `.env.example` values into `.env` and add the Firebase Web App configuration from Firebase Console.
2. Keep `firebase/serviceAccountKey.json` server-only. Rotate it immediately if it has ever been committed or shared.
3. Start the API:

```powershell
.\venv\Scripts\python.exe -m uvicorn app.api.main:app --reload
```

Open `http://127.0.0.1:8000/ui`. The browser signs in with Firebase Auth and sends only a verified ID token to the API. Groq credentials stay on the server.

The workflow supports weighted jobs, deterministic thresholds, bulk CV uploads, PDF/DOCX/TXT parsing, optional OCR for scanned PDFs, evidence-based Groq extraction and scoring, human overrides, and audit history.
