import os
import sys
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.common import ask_deepseek

load_dotenv()

def test_deepseek():
    print("🚀 Testing DeepSeek API integration...")
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("❌ DEEPSEEK_API_KEY not found in .env")
        return

    prompt = """
    Please correct the following ASR segment from a sermon.
    CONTEXT: Preacher is Stephen Tong (唐崇荣), Series is Ephesians (以弗所书).
    SEGMENT: 我们今天要讲的是以不所处第一章。
    
    Output JSON: {"data": "corrected text..."}
    """
    
    try:
        print("📤 Sending request to DeepSeek...")
        res = ask_deepseek(prompt)
        print("✅ Response received:")
        print("-" * 30)
        print(res)
        print("-" * 30)
    except Exception as e:
        print(f"❌ DeepSeek API Error: {e}")

if __name__ == "__main__":
    test_deepseek()
