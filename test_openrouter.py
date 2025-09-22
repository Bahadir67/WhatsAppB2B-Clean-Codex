#!/usr/bin/env python3
"""
OpenRouter API Test Script
Test if OpenRouter API key is working
"""

import os
import sys
from dotenv import load_dotenv

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load environment variables
load_dotenv()

def test_openrouter_api():
    """Test OpenRouter API connection"""
    
    api_key = os.getenv('OPENROUTER_API_KEY')
    model = os.getenv('OPENROUTER_MODEL', 'openai/gpt-4o-mini')
    
    print("=" * 50)
    print("OpenRouter API Test")
    print("=" * 50)
    
    print(f"API Key: {api_key[:20]}..." if api_key else "API Key: NOT FOUND")
    print(f"Model: {model}")
    print()
    
    if not api_key:
        print("❌ ERROR: OPENROUTER_API_KEY not found in .env file")
        return False
    
    try:
        from openai import OpenAI
        
        # Initialize OpenAI client with OpenRouter
        client = OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1"
        )
        
        # Test API call
        print("[TEST] Testing API connection...")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "user", "content": "Hello! This is a test message."}
            ],
            max_tokens=50
        )
        
        # Check response
        if response.choices:
            print("[SUCCESS] OpenRouter API is working!")
            print(f"Response: {response.choices[0].message.content}")
            print(f"Model used: {response.model}")
            print(f"Tokens used: {response.usage.total_tokens}")
            return True
        else:
            print("[ERROR] No response from API")
            return False
            
    except Exception as e:
        print(f"[ERROR] {str(e)}")
        
        # Specific error handling
        if "401" in str(e):
            print("→ Authentication error - check API key")
        elif "429" in str(e):
            print("→ Rate limit exceeded")
        elif "500" in str(e):
            print("→ Server error - try again later")
        
        return False

if __name__ == "__main__":
    success = test_openrouter_api()
    print("=" * 50)
    if success:
        print("✅ Test completed successfully!")
    else:
        print("❌ Test failed!")
    print("=" * 50)