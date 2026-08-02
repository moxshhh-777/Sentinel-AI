import os
import json
import logging
import asyncio
import requests
from typing import Type, TypeVar
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

from app.logging_config import get_logger

logger = get_logger("sentinel.llm")

# Set up defaults
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")

T = TypeVar("T", bound=BaseModel)

class GeminiClient:
    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model or GEMINI_MODEL

    async def generate_structured_output(self, prompt: str, schema: Type[T]) -> T:
        """
        Queries the Gemini API with a system prompt containing the Pydantic schema,
        and parses the returned JSON string directly into a Pydantic model.
        Executes HTTP requests in an executor to avoid blocking the asyncio loop.
        """
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY environment variable is not set.")

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"

        # Inject JSON schema instructions directly into the system prompt
        schema_json = json.dumps(schema.model_json_schema())
        system_instruction = (
            f"You are a precise financial decision-intelligence assistant. "
            f"You MUST return a JSON object that strictly conforms to this JSON schema:\n"
            f"{schema_json}\n"
            f"Do not wrap your output in markdown formatting (do NOT use ```json blocks). "
            f"Output ONLY raw JSON."
        )

        payload = {
            "contents": [
                {
                    "parts": [{"text": f"{system_instruction}\n\nInput Data and Task:\n{prompt}"}]
                }
            ],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1  # Highly deterministic
            }
        }

        headers = {"Content-Type": "application/json"}

        # Define connection callable
        def _post():
            import time
            # Stagger successive calls to prevent rate limits
            time.sleep(2.0)
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            return response.json()

        # Run blocking requests call in default executor thread pool
        loop = asyncio.get_running_loop()
        try:
            data = await loop.run_in_executor(None, _post)
            
            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError("No response candidates returned by Gemini API.")
                
            text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
            if not text:
                raise ValueError("Returned candidate content is empty.")

            # Clean potential markdown wrappers or backticks from response text
            cleaned_text = text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip("` \n\r\t")

            # Balance braces to truncate any trailing extra braces or markdown junk
            if cleaned_text.startswith("{"):
                brace_count = 0
                for i, char in enumerate(cleaned_text):
                    if char == "{":
                        brace_count += 1
                    elif char == "}":
                        brace_count -= 1
                        if brace_count == 0:
                            cleaned_text = cleaned_text[:i+1]
                            break

            # Parse raw JSON string into target Pydantic schema
            return schema.model_validate_json(cleaned_text)
            
        except Exception as e:
            logger.error(f"Gemini LLM wrapper execution failed: {e}")
            raise
