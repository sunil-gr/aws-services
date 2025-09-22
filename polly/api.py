import os
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse, HTMLResponse
from pydantic import BaseModel
from polly import PollyTTS

app = FastAPI(title="Polly TTS API")
app.add_middleware(
	CORSMiddleware,
	allow_origins=["*"],
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

@app.get("/", response_class=HTMLResponse)
def index():
	try:
		with open("frontend.html", "r", encoding="utf-8") as f:
			return f.read()
	except Exception:
		return HTMLResponse("<h1>Frontend not found</h1>", status_code=404)

@app.get("/userguide", response_class=HTMLResponse)
def userguide():
	try:
		with open("userguide.html", "r", encoding="utf-8") as f:
			return f.read()
	except Exception:
		return HTMLResponse("<h1>User guide not found</h1>", status_code=404)


class SynthesizeRequest(BaseModel):
	text: Optional[str] = None
	voice: Optional[str] = None
	gender: Optional[str] = None
	accent: Optional[str] = None
	format: str = "mp3"
	engine: Optional[str] = None
	language_code: Optional[str] = None
	sample_rate: Optional[int] = None
	style: Optional[str] = None


@app.get("/voices")
def get_voices(language_code: Optional[str] = None):
	tts = PollyTTS()
	voices = tts.list_voices(language_code=language_code)
	return [{
		"id": v["Id"],
		"name": v.get("Name", v["Id"]),
		"gender": v.get("Gender"),
		"language_code": v.get("LanguageCode"),
		"engines": v.get("SupportedEngines", [])
	} for v in voices]


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
):
	# Read text either from form or uploaded file
	if file is not None:
		filename = file.filename or "upload"
		if filename.lower().endswith(".pdf"):
			import PyPDF2
			reader = PyPDF2.PdfReader(file.file)
			buf = []
			for page in reader.pages:
				buf.append(page.extract_text() or "")
			text = "\n".join(buf)
		else:
			text = (await file.read()).decode("utf-8", errors="ignore")

	if not text or not text.strip():
		return JSONResponse({"error": "No text provided."}, status_code=400)

	tts = PollyTTS()
	voice_id = tts.select_voice(
		preferred_voice_id=voice,
		gender=gender,
		language_code=accent or language_code,
	)

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

	text_type = "text"
	# Note: SSML styles are disabled due to voice compatibility issues
	# if style:
	#     # Styles not currently supported - would need voice-specific SSML validation
	#     pass

	# Stream the synthesized audio back
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
				for audio in tts.synthesize(text, voice_id, "pcm", selected_engine, accent or language_code, actual_sr, text_type):
					wf.writeframes(audio)
			buf.seek(0)
			yield from buf
		else:
			for audio in tts.synthesize(text, voice_id, format, selected_engine, accent or language_code, sample_rate, text_type):
				yield audio

	media_type = {
		"mp3": "audio/mpeg",
		"ogg_vorbis": "audio/ogg",
		"pcm": "audio/L16",
		"wav": "audio/wav",
	}.get(format, "application/octet-stream")

	return StreamingResponse(iter_audio(), media_type=media_type, headers={
		"Content-Disposition": f"attachment; filename=polly_output.{format}"
	})


if __name__ == "__main__":
	import uvicorn
	uvicorn.run("api:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=False)


