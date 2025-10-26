#!/usr/bin/env python3
"""
Simple test script to verify download functionality
"""
import os
import sys
import asyncio

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the download functions from whatsapp_bot
from whatsapp_bot import (
    get_media_info,
    detect_platform,
    ensure_directories
)

async def test_simple_download():
    """Test simple download functionality"""
    print("🚀 Testing simple download functionality")
    print("=" * 50)
    
    # Ensure directories exist
    ensure_directories()
    
    # Test URL - a simple YouTube video
    test_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"  # Rick Astley - Never Gonna Give You Up
    
    try:
        print(f"Testing URL: {test_url}")
        
        # Detect platform
        platform = detect_platform(test_url)
        print(f"Platform detected: {platform}")
        
        if not platform:
            print("❌ Could not detect platform")
            return False
            
        # Get media info
        print("Extracting media info...")
        info = await get_media_info(test_url)
        
        if info:
            print(f"✅ Media info extracted successfully")
            print(f"Title: {info.get('title', 'Unknown')}")
            print(f"Uploader: {info.get('uploader', 'Unknown')}")
            print(f"Content type: {info.get('content_type', 'Unknown')}")
            return True
        else:
            print("❌ Failed to extract media info")
            return False
            
    except Exception as e:
        print(f"❌ Error testing download: {str(e)}")
        return False

async def main():
    """Main test function"""
    print("🧪 WhatsApp Bot Simple Test")
    print("=" * 30)
    
    success = await test_simple_download()
    
    print("\n" + "=" * 30)
    if success:
        print("✅ Simple test passed!")
        print("🎉 The WhatsApp bot download functionality is working correctly.")
    else:
        print("❌ Simple test failed!")
        print("⚠️  Please check the errors above.")

if __name__ == "__main__":
    asyncio.run(main())