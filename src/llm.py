import ollama
from typing import Optional

class LLMService:
    def __init__(self, model: str = "gemma3:12b-it-qat"):
        self.model = model

    def clean_slug(self, text: str) -> str:
        """Removes all special characters and spaces, replaces with underscore."""
        if not text:
            return ""
        # Remove non-alphanumeric/spaces/underscores/hyphens
        import re
        text = re.sub(r'[^a-zA-Z0-9\s_-]', '', text)
        # Replace spaces/hyphens with underscore
        text = re.sub(r'[-\s]+', '_', text).strip('_')
        return text

    def translate_to_english(self, text: str) -> str:
        """Translates short text (names, titles) to English using LLM."""
        if not text:
            return ""
        
        prompt = f"Translate the following Chinese text to a concise and proper English name/title, specialized for Bible/Sermon contexts. Return ONLY the English translation, no punctuation or extra text.\n\nText: {text}"
        
        try:
            response = ollama.generate(model=self.model, prompt=prompt)
            return response.get("response", "").strip().strip('"').strip("'")
        except Exception as e:
            print(f"Error calling Ollama: {e}")
            return text

    def refine_sermon_metadata(self, sermon_data: dict, preacher_name: str) -> Optional[dict]:
        """Refines existing sermon metadata with Bible context awareness."""
        prompt = f"""
Refine the following sermon metadata for accuracy in a Bible context.
Original Preacher Name: {preacher_name}
Sermon Title (Original): {sermon_data.get('title')}
Sermon Series (Original): {sermon_data.get('series', {}).get('name')}
Current Title (English): {sermon_data.get('title_en')}
Current Series (English): {sermon_data.get('series', {}).get('name_en')}

Return a JSON object with these EXACT fields:
- preacher_en: English name of preacher (no spaces, e.g., "StevenTong").
- title_en: Corrected Bible-context English title (can have spaces).
- series_en: Corrected Bible book or series name (proper English, e.g., "Luke").
- chapter: Bible chapter (integer).
- verse_start: Start verse (integer).
- verse_end: End verse (integer).
- scripture_reference: Proper reference (e.g., "Luke 1:5-10").

RULES:
1. Ensure the Bible book name is the standard English name (e.g., "Leviticus" not "Li Wei Ji").
2. DO NOT include special characters like : / \ * ? " < > | in any field.
3. If no scripture is found, set chapter/verse to 0.

Return ONLY the JSON.
"""
        try:
            response = ollama.generate(model=self.model, prompt=prompt, format="json")
            import json
            return json.loads(response.get("response", "{}"))
        except Exception as e:
            print(f"Error refining metadata: {e}")
            return None
