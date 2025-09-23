import os
import io
from typing import Iterable, List, Optional
import boto3
try:
	from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover
	load_dotenv = None


class PollyTTS:
	"""Lightweight AWS Polly wrapper with sane defaults and file output helpers."""

	def __init__(
		self,
		region_name: Optional[str] = None,
		aws_access_key_id: Optional[str] = None,
		aws_secret_access_key: Optional[str] = None,
		aws_session_token: Optional[str] = None,
	):
		# Load .env if python-dotenv is available
		if load_dotenv is not None:
			load_dotenv()
		# Prefer boto3's default credential/provider chain; allow explicit override via args/env
		self.client = boto3.client(
			"polly",
			region_name=region_name or os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION") or "us-east-1",
			aws_access_key_id=aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID"),
			aws_secret_access_key=aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY"),
			aws_session_token=aws_session_token or os.getenv("AWS_SESSION_TOKEN"),
		)

	def list_voices(self, language_code: Optional[str] = None) -> List[dict]:
		params = {}
		if language_code:
			params["LanguageCode"] = language_code
		voices = []
		response = self.client.describe_voices(**params)
		voices.extend(response.get("Voices", []))
		while response.get("NextToken"):
			params["NextToken"] = response["NextToken"]
			response = self.client.describe_voices(**params)
			voices.extend(response.get("Voices", []))
		return voices

	def select_voice(
		self,
		preferred_voice_id: Optional[str] = None,
		gender: Optional[str] = None,
		language_code: Optional[str] = None,
	) -> str:
		"""Return a VoiceId based on explicit id or gender/language preference."""
		if preferred_voice_id:
			return preferred_voice_id
		voices = self.list_voices(language_code=language_code)
		if gender:
			gender_norm = gender.strip().lower()
			voices = [v for v in voices if v.get("Gender", "").lower() == gender_norm]
		if not voices:
			# Fallback to global voice list
			voices = self.list_voices()
			if gender:
				voices = [v for v in voices if v.get("Gender", "").lower() == gender_norm]
		# Prefer neural-supported voices when possible
		for v in voices:
			if "neural" in [e.lower() for e in v.get("SupportedEngines", [])]:
				return v["Id"]
		# Otherwise first match
		return voices[0]["Id"] if voices else "Joanna"

	def _chunk_text(self, text: str, max_len: int = 2900) -> List[str]:
		# Polly limit is ~3000 characters for Text; keep safety margin
		if len(text) <= max_len:
			return [text]
		chunks: List[str] = []
		start = 0
		while start < len(text):
			end = min(start + max_len, len(text))
			# try to split on whitespace/punctuation boundaries when possible
			slice_text = text[start:end]
			if end < len(text):
				last_break = max(slice_text.rfind("\n"), slice_text.rfind(". "), slice_text.rfind(" "))
				if last_break > 0:
					end = start + last_break + 1
					slice_text = text[start:end]
			chunks.append(slice_text)
			start = end
		return chunks

	def synthesize(
		self,
		text: str,
		voice_id: str = "Joanna",
		output_format: str = "mp3",
		engine: Optional[str] = None,
		language_code: Optional[str] = None,
		sample_rate: Optional[int] = None,
		text_type: str = "text",
	) -> Iterable[bytes]:
		"""Yield raw audio bytes for each chunk. Concatenate for full audio.

		output_format: "mp3", "ogg_vorbis", or "pcm"
		engine: None/"standard" or "neural" (if the voice supports it)
		"""
		if output_format not in ("mp3", "ogg_vorbis", "pcm"):
			raise ValueError("output_format must be 'mp3', 'ogg_vorbis', or 'pcm'")
		params = {
			"OutputFormat": output_format,
			"VoiceId": voice_id,
		}
		if engine:
			params["Engine"] = engine
		if language_code:
			params["LanguageCode"] = language_code
		if sample_rate is not None:
			params["SampleRate"] = str(sample_rate)
		if text_type in ("text", "ssml"):
			params["TextType"] = text_type
		for chunk in self._chunk_text(text):
			response = self.client.synthesize_speech(Text=chunk, **params)
			yield response["AudioStream"].read()

	def synthesize_to_file(
		self,
		text: str,
		output_path: str,
		voice_id: str = "Joanna",
		output_format: str = "mp3",
		engine: Optional[str] = None,
		language_code: Optional[str] = None,
		sample_rate: Optional[int] = None,
		text_type: str = "text",
	) -> str:
		"""Synthesize full text and write to a single file. Returns output path.

		Note: For "mp3" and "ogg_vorbis", concatenation is usually safe. For "pcm",
		you may need to post-process into a container (e.g., WAV) for proper headers.
		"""
		# Ensure directory exists
		os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
		# If WAV requested, synthesize PCM and wrap with proper WAV headers for best compatibility
		if output_format == "wav":
			import wave
			actual_sample_rate = sample_rate or 16000
			with wave.open(output_path, "wb") as wf:
				wf.setnchannels(1)
				wf.setsampwidth(2)  # 16-bit PCM
				wf.setframerate(actual_sample_rate)
				for audio_bytes in self.synthesize(
					text=text,
					voice_id=voice_id,
					output_format="pcm",
					engine=engine,
					language_code=language_code,
					sample_rate=actual_sample_rate,
					text_type=text_type,
				):
					wf.writeframes(audio_bytes)
			return output_path
		# Non-WAV: write raw stream bytes
		with open(output_path, "wb") as f:
			for audio_bytes in self.synthesize(
				text=text,
				voice_id=voice_id,
				output_format=output_format,
				engine=engine,
				language_code=language_code,
				sample_rate=sample_rate,
				text_type=text_type,
			):
				f.write(audio_bytes)
		return output_path


def main_cli():
	import argparse
	parser = argparse.ArgumentParser(description="Synthesize speech with Amazon Polly")
	group = parser.add_mutually_exclusive_group(required=True)
	group.add_argument("--text", help="Text to synthesize")
	group.add_argument("--input-file", help="Path to a UTF-8 text file or PDF file")
	parser.add_argument("--voice", help="VoiceId, e.g., Joanna, Matthew")
	parser.add_argument("--gender", choices=["male", "female"], help="Auto-select a voice by gender")
	parser.add_argument("--accent", help="Language/accent code, e.g., en-US, en-GB, en-AU, en-IN")
	parser.add_argument("--format", default="mp3", choices=["mp3", "ogg_vorbis", "pcm", "wav"], help="Output audio format")
	parser.add_argument("--engine", choices=["standard", "neural"], help="Polly engine if supported")
	parser.add_argument("--language-code", help="Override language code, e.g., en-US")
	parser.add_argument("--style", choices=["conversational", "newscaster", "narration"], help="Speaking style (requires Neural-supported voices)")
	parser.add_argument("--sample-rate", type=int, help="Desired sample rate in Hz (e.g., 16000, 22050)")
	parser.add_argument("--output", required=True, help="Output audio file path, e.g., out.mp3")
	parser.add_argument("--list-voices", action="store_true", help="List available voices and exit")
	args = parser.parse_args()

	if args.list_voices:
		tts = PollyTTS()
		voices = tts.list_voices(language_code=args.accent or args.language_code)
		for v in voices:
			engines = ",".join(v.get("SupportedEngines", []))
			print(f"{v['Id']}\t{v['Gender']}\t{v.get('LanguageCode','')}\t{engines}")
		return

	if args.input_file:
		# Check if it's a PDF file
		if args.input_file.lower().endswith('.pdf'):
			try:
				import PyPDF2
				with open(args.input_file, 'rb') as pdf_file:
					pdf_reader = PyPDF2.PdfReader(pdf_file)
					text = ""
					for page in pdf_reader.pages:
						text += page.extract_text() + "\n"
			except ImportError:
				raise SystemExit("PyPDF2 not installed. Run: pip install PyPDF2")
			except Exception as e:
				raise SystemExit(f"Error reading PDF: {e}")
		else:
			# Regular text file
			with open(args.input_file, "r", encoding="utf-8") as rf:
				text = rf.read()
	else:
		text = args.text or ""

	if not text.strip():
		raise SystemExit("No text provided.")

	tts = PollyTTS()
	# Resolve voice by precedence: explicit --voice > gender/accent selection > default
	voice_id = tts.select_voice(
		preferred_voice_id=args.voice,
		gender=args.gender,
		language_code=args.accent or args.language_code,
	)

	# If style is specified, wrap text in SSML with the chosen domain
	text_type = "text"
	if args.style:
		domain_map = {
			"conversational": "conversational",
			"newscaster": "news",
			"narration": "narration",
		}
		domain = domain_map[args.style]
		lang = args.accent or args.language_code or "en-US"
		# Wrap each chunk later; here we prepare the whole string. Chunking happens after.
		text = f"<speak><lang xml:lang=\"{lang}\"><amazon:domain name=\"{domain}\">{text}</amazon:domain></lang></speak>"
		text_type = "ssml"

	path = tts.synthesize_to_file(
		text=text,
		output_path=args.output,
		voice_id=voice_id,
		output_format=args.format,
		engine=args.engine,
		language_code=args.accent or args.language_code,
		sample_rate=args.sample_rate,
		text_type=text_type,
	)
	print(path)


if __name__ == "__main__":
	main_cli()