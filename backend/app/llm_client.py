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
        # Initialize Gemini API key and model properties, defaulting to loaded environment parameters
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

        # Inject JSON schema instructions directly into the system prompt by converting Pydantic models to standard JSON schema representation
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
                "temperature": 0.1  # Highly deterministic to ensure strict schema compliance
            }
        }

        headers = {"Content-Type": "application/json"}

        # Define connection callable
        def _post():
            import time
            import random
            max_attempts = 6
            backoff = 8.0
            
            for attempt in range(max_attempts):
                # Add random jitter stagger to prevent parallel calls thundering herd rate limit
                sleep_dur = 1.0 + random.uniform(0.5, 3.5)
                time.sleep(sleep_dur)
                try:
                    response = requests.post(url, json=payload, headers=headers, timeout=30)
                    if response.status_code == 429:
                        if attempt == max_attempts - 1:
                            response.raise_for_status()
                        # Add jitter to backoff sleep as well
                        retry_dur = backoff + random.uniform(0.5, 2.0)
                        logger.warning(
                            f"Gemini API rate limited (429). Retrying in {retry_dur:.1f} seconds "
                            f"(Attempt {attempt + 1}/{max_attempts})..."
                        )
                        time.sleep(retry_dur)
                        backoff *= 2.0
                        continue
                    response.raise_for_status()
                    return response.json()
                except requests.exceptions.RequestException as e:
                    if attempt == max_attempts - 1:
                        raise e
                    retry_dur = backoff + random.uniform(0.5, 2.0)
                    logger.warning(f"Gemini API request failed: {e}. Retrying in {retry_dur:.1f} seconds...")
                    time.sleep(retry_dur)
                    backoff *= 2.0

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

            # Parse raw JSON string into target Pydantic schema
            try:
                return schema.model_validate_json(cleaned_text)
            except Exception as primary_err:
                logger.warning(f"Primary JSON validation failed: {primary_err}. Attempting self-healing JSON repair...")
                
                # Self-healing helper for truncated JSON
                def repair_json(json_str: str) -> str:
                    """
                    Analyzes and repairs truncated or malformed JSON payloads
                    returned from the LLM by matching unclosed brackets, braces, and open quotes.
                    """
                    json_str = json_str.strip()
                    if not json_str:
                        return json_str
                    open_brackets = []
                    in_string = False
                    escaped = False
                    for char in json_str:
                        if char == '"' and not escaped:
                            in_string = not in_string
                        elif char == '\\' and in_string:
                            escaped = not escaped
                            continue
                        elif not in_string:
                            if char in ("{", "["):
                                open_brackets.append(char)
                            elif char in ("}", "]"):
                                if open_brackets:
                                    open_brackets.pop()
                        escaped = False
                    if in_string:
                        json_str += '"'
                    if open_brackets:
                        json_str = json_str.rstrip(", \n\r\t")
                        close_str = ""
                        for b in reversed(open_brackets):
                            if b == "{":
                                close_str += "}"
                            elif b == "[":
                                close_str += "]"
                        json_str += close_str
                    return json_str

                try:
                    repaired_text = repair_json(cleaned_text)
                    return schema.model_validate_json(repaired_text)
                except Exception as repair_err:
                    logger.error(f"Structured output parsing failed even after repair. Raw LLM output:\n{text}")
                    raise primary_err
            
        except Exception as e:
            logger.error(f"Gemini LLM wrapper execution failed: {e}")
            raise
