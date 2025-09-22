## AWS Polly Text-to-Speech (Python)

This project provides a simple, production-friendly integration with Amazon Polly using Python. It includes:

- A reusable `PollyTTS` wrapper in `polly.py`
- CLI usage via `polly.py` or `polly_text_to_speech.py`
- `.env` support (optional) and standard AWS credential chain

### Prerequisites

- Python 3.9+ installed
- An AWS account with permissions for Polly (`polly:SynthesizeSpeech`, `polly:DescribeVoices`)
- AWS credentials configured via one of:
  - AWS CLI profile (`aws configure`) or SSO
  - Environment variables in `.env`/system

### Setup (Windows PowerShell)

```powershell
cd D:\xampp\htdocs\hm\polly
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Optional: set environment variables in `.env` (auto-loaded if present):

```env
# .env (example)
AWS_ACCESS_KEY_ID=YOUR_KEY
AWS_SECRET_ACCESS_KEY=YOUR_SECRET
AWS_REGION=us-east-1
```

### Usage

- Direct text:

```powershell
python polly.py --text "Hello from Polly" --voice Joanna --format mp3 --output out.mp3
```

- From file:

```powershell
python polly.py --input-file input.txt --voice Matthew --engine neural --output out.mp3
```

- Alternative entry point:

```powershell
python polly_text_to_speech.py --text "Hi" --output speech.mp3
```

#### Selecting gender, accent, and style

- List voices by language/accent and gender:

```powershell
python polly.py --list-voices --accent en-US
```

- Auto-select a male/female voice with accent:

```powershell
python polly.py --text "Hi" --gender male --accent en-GB --engine neural --output uk_male.mp3
```

- Explicit voice with a speaking style (Neural voices):

```powershell
python polly.py --text "Breaking news now" --voice Matthew --style newscaster --engine neural --output news.mp3
```

#### Portuguese output (Portugal/Brazil)

- List available Portuguese voices:

```powershell
python polly.py --list-voices --accent pt-PT
python polly.py --list-voices --accent pt-BR
```

- Auto-select a Portuguese voice by accent (engine auto-selected):

```powershell
# European Portuguese
python polly.py --text "Olá, bem-vindo ao Amazon Polly" --accent pt-PT --format wav --sample-rate 16000 --output ptpt.wav

# Brazilian Portuguese (Neural if supported)
python polly.py --text "Olá, bem-vindo ao Amazon Polly" --accent pt-BR --engine neural --output ptbr.mp3
```

### Compatibility: MP3/MP4 players

Some players (especially on older devices or browsers) may not support certain MP3 encodings or any audio inside MP4 containers. For maximum compatibility, generate WAV output:

```powershell
# 16 kHz mono WAV (very compatible for telephony/embedded players)
python polly.py --text "Hello" --format wav --sample-rate 16000 --output out.wav

# Higher fidelity WAV
python polly.py --text "Hello" --format wav --sample-rate 22050 --output out.wav
```

Notes:
- `--format wav` produces a PCM WAV with correct headers. Internally it requests `pcm` from Polly and writes a proper WAV container.
- For MP4 video containers, ensure your player supports the audio codec used; this project outputs audio only. If you need MP4, mux the audio into video with a compatible codec using a tool like ffmpeg.

### Voice listing (programmatic)

```python
from polly import PollyTTS
tts = PollyTTS()
voices = tts.list_voices()
print(len(voices), "voices available")
```

### Notes

- Credentials: By default, `boto3` uses the standard AWS provider chain. `.env` is optional.
- Long text is chunked automatically to stay within Polly limits.
- Supported formats: `mp3`, `ogg_vorbis`, `pcm`. For `pcm`, post-process to WAV if needed.

### Run the API and Web UI

Start the FastAPI server (serves the React UI at `/` and the user guide at `/userguide`):

```powershell
cd D:\xampp\htdocs\hm\polly
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn api:app --host 0.0.0.0 --port 8001
```

Open in your browser:

- App UI: `http://localhost:8001/`
- User Guide: `http://localhost:8001/userguide`

Test with curl (download to current folder):

```powershell
# List voices for US English
curl "http://localhost:8001/voices?language_code=en-US"

# Synthesize WAV (auto-selects supported engine)
curl -X POST "http://localhost:8001/synthesize" ^
  -F "text=Hello from Polly" ^
  -F "format=wav" ^
  -o hello.wav
```

Notes:
- The API streams audio to the client (not saved on server). Use the browser download or `-o filename` with curl.
- If you need server-side saving under `audio/`, ask and we’ll enable it.


