import os
from typing import Iterable, List, Optional

import boto3
try:
	from dotenv import load_dotenv  # type: ignore
except Exception:
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
		if load_dotenv is not None:
			load_dotenv()
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
		voices: List[dict] = []
		resp = self.client.describe_voices(**params)
		voices.extend(resp.get("Voices", []))
		while resp.get("NextToken"):
			params["NextToken"] = resp["NextToken"]
			resp = self.client.describe_voices(**params)
			voices.extend(resp.get("Voices", []))
		return voices

	def select_voice(
		self,
		preferred_voice_id: Optional[str] = None,
		gender: Optional[str] = None,
		language_code: Optional[str] = None,
	) -> str:
		if preferred_voice_id:
			return preferred_voice_id
		voices = self.list_voices(language_code=language_code)
		if gender:
			g = gender.strip().lower()
			voices = [v for v in voices if v.get("Gender", "").lower() == g]
		if not voices:
			voices = self.list_voices()
			if gender:
				g = gender.strip().lower()
				voices = [v for v in voices if v.get("Gender", "").lower() == g]
		for v in voices:
			if "neural" in [e.lower() for e in v.get("SupportedEngines", [])]:
				return v["Id"]
		return voices[0]["Id"] if voices else "Joanna"

	def _chunk_text(self, text: str, max_len: int = 2900) -> List[str]:
		if len(text) <= max_len:
			return [text]
		chunks: List[str] = []
		start = 0
		while start < len(text):
			end = min(start + max_len, len(text))
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
		voice_id: str,
		output_format: str = "mp3",
		engine: Optional[str] = None,
		language_code: Optional[str] = None,
		sample_rate: Optional[int] = None,
		text_type: str = "text",
	) -> Iterable[bytes]:
		if output_format not in ("mp3", "ogg_vorbis", "pcm"):
			raise ValueError("output_format must be 'mp3', 'ogg_vorbis', or 'pcm'")
		params = {"OutputFormat": output_format, "VoiceId": voice_id}
		if engine:
			params["Engine"] = engine
		if language_code:
			params["LanguageCode"] = language_code
		if sample_rate is not None:
			params["SampleRate"] = str(sample_rate)
		if text_type in ("text", "ssml"):
			params["TextType"] = text_type
		for chunk in self._chunk_text(text):
			resp = self.client.synthesize_speech(Text=chunk, **params)
			yield resp["AudioStream"].read()


