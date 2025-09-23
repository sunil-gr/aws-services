import os
from typing import Optional
import html
import requests


class GoogleTranslator:
	"""Minimal Google Cloud Translation (v2 REST) client using an API key.

	Set GOOGLE_API in environment with a valid API key (for Translate API).
	"""

	def __init__(self, api_key: Optional[str] = None):
		self.api_key = api_key or os.getenv("GOOGLE_API")
		if not self.api_key:
			raise RuntimeError("GOOGLE_API environment variable not set")
		self.endpoint = "https://translation.googleapis.com/language/translate/v2"

	def translate_text(self, text: str, source: Optional[str], target: str) -> str:
		params = {"key": self.api_key}
		data = {
			"q": text,
			"target": target,
		}
		if source:
			data["source"] = source
		resp = requests.post(self.endpoint, params=params, json=data, timeout=30)
		resp.raise_for_status()
		payload = resp.json()
		translated = payload["data"]["translations"][0]["translatedText"]
		# Google may return HTML-escaped entities; unescape before sending to Polly
		return html.unescape(translated)


