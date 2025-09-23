## Backend API (recreated)

This repo includes a new backend under `backend/` with:
- `backend/polly_tts.py`: Polly wrapper
- `backend/translate.py`: Google Cloud Translation (v2 REST) via API key in `GOOGLE_API`
- `backend/api.py`: FastAPI server. If `src_lang != dst_lang`, text is translated before TTS.

### Backend setup

```powershell
cd D:\xampp\htdocs\hm\polly\backend
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Env (example)
$env:AWS_REGION = "us-east-1"
$env:GOOGLE_API = "YOUR_GOOGLE_TRANSLATE_API_KEY"

python -m uvicorn backend.api:app --host 0.0.0.0 --port 8001
```

### API usage (translation + TTS)

- Translate en-IN to pt-PT and synthesize WAV:

```powershell
curl -X POST "http://localhost:8001/synthesize" ^
  -F "text=Hello, how are you?" ^
  -F "src_lang=en-IN" ^
  -F "dst_lang=pt-PT" ^
  -F "format=wav" ^
  -o out.wav
```

- Keep language same (no translation), choose voice/gender:

```powershell
curl -X POST "http://localhost:8001/synthesize" ^
  -F "text=Olá, bem-vindo" ^
  -F "dst_lang=pt-PT" ^
  -F "gender=female" ^
  -F "format=mp3" ^
  -o out.mp3
```

Notes:
- Requires a valid `GOOGLE_API` key with Translate API enabled.
- Audio is streamed; not saved server-side.
