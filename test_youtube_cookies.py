#!/usr/bin/env python3
"""
Test script to verify YouTube cookies loading and usage
"""
import os
import sys
import asyncio

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the validation functions from whatsapp_bot
from whatsapp_bot import (
    validate_youtube_setup,
    YOUTUBE_COOKIES_FILE
)

async def test_youtube_cookies():
    """Test YouTube cookies loading and validation"""
    print("🔍 Testing YouTube cookies loading and validation")
    print("=" * 50)
    
    # Check if file exists
    print(f"Checking YouTube cookies file: {YOUTUBE_COOKIES_FILE}")
    if os.path.exists(YOUTUBE_COOKIES_FILE):
        print(f"✅ File exists")
        size = os.path.getsize(YOUTUBE_COOKIES_FILE)
        print(f"📁 File size: {size} bytes")
        
        if size > 0:
            print("✅ File is not empty")
            
            # Try to read file
            try:
                with open(YOUTUBE_COOKIES_FILE, 'r') as f:
                    content = f.read()
                    print(f"📝 File content preview: {content[:100]}...")
                    
                    # Check for common YouTube cookie identifiers
                    if 'youtube' in content.lower() or 'google' in content.lower():
                        print("✅ File contains YouTube/Google cookies")
                    else:
                        print("⚠️ File may not contain YouTube cookies")
                        
            except Exception as e:
                print(f"❌ Error reading file: {e}")
        else:
            print("❌ File is empty")
    else:
        print("❌ File does not exist")
    
    print("\n" + "=" * 50)
    print("Running validation function...")
    
    # Run the validation function
    try:
        result = await validate_youtube_setup()
        if result:
            print("✅ YouTube validation passed")
        else:
            print("❌ YouTube validation failed")
    except Exception as e:
        print(f"❌ Error during validation: {e}")

async def main():
    """Main test function"""
    print("🧪 WhatsApp Bot YouTube Cookies Test")
    print("=" * 35)
    
    await test_youtube_cookies()
    
    print("\n" + "=" * 35)
    print("Test completed!")

if __name__ == "__main__":
    asyncio.run(main())