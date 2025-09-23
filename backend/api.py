import os
import logging
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse

# Assuming polly_tts and translate are your local modules
try:
    from .polly_tts import PollyTTS
    from .translate import GoogleTranslator
except Exception:
    # Fallback to local imports when running as a script from the backend directory
    import sys as _sys, os as _os
    _sys.path.append(_os.path.dirname(__file__))
    from polly_tts import PollyTTS  # type: ignore
    from translate import GoogleTranslator  # type: ignore

app = FastAPI(title="Polly TTS API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn.error")
app_logger = logging.getLogger("polly.app")

# Endpoint to fetch available voices
@app.get("/voices")
def get_voices(language_code: Optional[str] = None):
    tts = PollyTTS()
    voices = tts.list_voices(language_code=language_code)
    return [{
        "id": v["Id"],
        "name": v.get("Name", v["Id"]),
        "gender": v.get("Gender"),
        "language_code": v.get("LanguageCode"),
        "engines": v.get("SupportedEngines", []),
    } for v in voices]


# Endpoint to synthesize speech
@app.post("/synthesize")
async def synthesize(
    text: Optional[str] = Form(None),
    voice: Optional[str] = Form(None),
    gender: Optional[str] = Form(None),
    accent: Optional[str] = Form(None),
    format: str = Form("mp3"),
    engine: Optional[str] = Form(None),
    language_code: Optional[str] = Form(None),
    sample_rate: Optional[int] = Form(None),
    style: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    src_lang: Optional[str] = Form(None),
    dst_lang: Optional[str] = Form(None)
):
    # Log incoming request params (languages, voice hints)
    app_logger.info("[Request] src_lang=%s dst_lang=%s voice=%s gender=%s format=%s engine=%s",
                    src_lang, dst_lang, voice, gender, format, engine)

    # Read input text (from file or form)
    if file is not None and not text:
        filename = file.filename or "upload"
        if filename.lower().endswith(".pdf"):
            import PyPDF2
            reader = PyPDF2.PdfReader(file.file)
            text = "\n".join([(p.extract_text() or "") for p in reader.pages])
        else:
            text = (await file.read()).decode("utf-8", errors="ignore")

    if not text or not text.strip():
        return JSONResponse({"error": "No text provided."}, status_code=400)

    # Translate if needed
    translated_flag = False
    if src_lang and dst_lang and src_lang != dst_lang:
        try:
            translator = GoogleTranslator()
            translated = translator.translate_text(text, source=src_lang, target=dst_lang)
            preview = translated[:500] + "..." if len(translated) > 500 else translated
            logger.info("[Translate] %s -> %s (len=%d): %s", src_lang, dst_lang, len(translated), preview)
            text = translated
            translated_flag = True
        except Exception as e:
            logger.error("[Translate] Translation failed: %s", str(e))
            return JSONResponse({"error": f"Translation failed: {e}"}, status_code=500)
    else:
        lang = dst_lang or src_lang or "unknown"
        preview = text[:500] + "..." if len(text) > 500 else text
        logger.info("[No-Translate] using language=%s (len=%d): %s", lang, len(text), preview)

    # Synthesize speech using PollyTTS
    tts = PollyTTS()
    voice_id = tts.select_voice(preferred_voice_id=voice, gender=gender, language_code=dst_lang or accent or language_code)

    # Determine a supported engine for the selected voice (prefer neural)
    selected_engine = engine
    try:
        voice_catalog = tts.list_voices()
        voice_info = next((v for v in voice_catalog if v.get("Id") == voice_id), None)
        if voice_info:
            supported = [e.lower() for e in voice_info.get("SupportedEngines", [])]
            if not supported:
                selected_engine = None
            elif selected_engine and selected_engine.lower() not in supported:
                # override to a supported engine
                selected_engine = "neural" if "neural" in supported else ("standard" if "standard" in supported else None)
            elif not selected_engine:
                selected_engine = "neural" if "neural" in supported else ("standard" if "standard" in supported else None)
    except Exception:
        # If anything fails, fall back to user-provided engine
        selected_engine = engine

    # Audio synthesis function
    def iter_audio():
        if format == "wav":
            import io as _io
            import wave
            actual_sr = sample_rate or 16000
            buf = _io.BytesIO()
            with wave.open(buf, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(actual_sr)
                for audio in tts.synthesize(text, voice_id, "pcm", selected_engine, dst_lang or accent or language_code, actual_sr, "text"):
                    wf.writeframes(audio)
            buf.seek(0)
            yield from buf
        else:
            for audio in tts.synthesize(text, voice_id, format, selected_engine, dst_lang or accent or language_code, sample_rate, "text"):
                yield audio

    media_type = {
        "mp3": "audio/mpeg",
        "ogg_vorbis": "audio/ogg",
        "pcm": "audio/L16",
        "wav": "audio/wav",
    }.get(format, "application/octet-stream")

    # Response headers with useful metadata
    resp_headers = {
        "Content-Disposition": f"attachment; filename=polly_output.{format}",
        "X-Src-Lang": src_lang or "",
        "X-Dst-Lang": dst_lang or "",
        "X-Translated": "true" if translated_flag else "false",
        "X-Voice-Id": voice_id or "",
    }

    return StreamingResponse(iter_audio(), media_type=media_type, headers=resp_headers)




if __name__ == "__main__":
    import uvicorn
    # Allow running either from repo root (use backend.api) or inside backend/ (use api)
    module_path = "backend.api:app" if __package__ else "api:app"
    uvicorn.run(module_path, host="0.0.0.0", port=int(os.getenv("PORT", 8001)), reload=False)
