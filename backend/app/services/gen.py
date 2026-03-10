import os
from dotenv import load_dotenv

import google.generativeai as genai

# Load environment variables
load_dotenv()

# Configure the API key
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("GEMINI_API_KEY not found in environment variables")

genai.configure(api_key=api_key)

def get_gemini_response(prompt: str, model: str = "gemini-flash-1.5") -> str:
    """
    Get a response from Google Gemini API.
    
    Args:
        prompt: The input prompt for the model
        model: The model to use (default: gemini-flash-1.5)
    
    Returns:
        The response text from Gemini
    """
    try:
        model_instance = genai.GenerativeModel(model)
        response = model_instance.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {str(e)}"
