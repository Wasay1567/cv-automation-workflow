import os
from dotenv import load_dotenv
from google import genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

_gemini_client = genai.Client(api_key=api_key)

def get_gemini_response(prompt: str, model: str = "gemma-4-26b-a4b-it") -> str:
    try:
        if _gemini_client is not None:
            response = _gemini_client.models.generate_content(model=model, contents=prompt)
            return response.text or ""
        else:
            return ""

    except Exception as e:
        return f"Error: {str(e)}"
