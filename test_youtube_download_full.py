#!/usr/bin/env python3
"""
Comprehensive test script to verify YouTube download functionality with cookies
"""
import os
import sys
import asyncio

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the download functions from whatsapp_bot
from whatsapp_bot import (
    get_media_info,
    download_media,
    detect_platform,
    ensure_directories,
    YOUTUBE_COOKIES_FILE
)

async def test_youtube_download_with_cookies():
    """Test YouTube download functionality with cookies"""
    print("🚀 Testing YouTube download with cookies")
    print("=" * 50)
    
    # Ensure directories exist
    ensure_directories()
    
    # Check YouTube cookies
    print(f"Checking YouTube cookies file: {YOUTUBE_COOKIES_FILE}")
    if os.path.exists(YOUTUBE_COOKIES_FILE):
        size = os.path.getsize(YOUTUBE_COOKIES_FILE)
        print(f"✅ YouTube cookies file exists ({size} bytes)")
    else:
        print("❌ YouTube cookies file not found")
        return False
    
    # Test URLs - using a simple, well-known YouTube video
    test_urls = [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",  # Rick Astley - Never Gonna Give You Up
    ]
    
    for i, test_url in enumerate(test_urls, 1):
        print(f"\n--- Test {i} ---")
        print(f"Testing URL: {test_url}")
        
        try:
            # Detect platform
            platform = detect_platform(test_url)
            print(f"Platform detected: {platform}")
            
            if not platform:
                print("❌ Could not detect platform")
                continue
                
            # Get media info with cookies
            print("Extracting media info with cookies...")
            info = await get_media_info(test_url)
            
            if info:
                print(f"✅ Media info extracted successfully")
                print(f"Title: {info.get('title', 'Unknown')}")
                print(f"Uploader: {info.get('uploader', 'Unknown')}")
                print(f"Content type: {info.get('content_type', 'Unknown')}")
                
                # Try to download the media
                print("Downloading media...")
                file_path = await download_media(test_url, quality="360p", audio_only=False, info=info)
                
                if file_path and os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    size_mb = file_size / (1024 * 1024)
                    print(f"✅ Download successful: {file_path} ({size_mb:.1f} MB)")
                    
                    # Clean up the downloaded file
                    os.remove(file_path)
                    print("✅ Cleaned up downloaded file")
                    return True
                else:
                    print("❌ Download failed")
                    return False
            else:
                print("❌ Failed to extract media info")
                return False
                
        except Exception as e:
            print(f"❌ Error testing download: {str(e)}")
            return False
    
    return True

async def main():
    """Main test function"""
    print("🧪 WhatsApp Bot YouTube Download Test")
    print("=" * 40)
    
    success = await test_youtube_download_with_cookies()
    
    print("\n" + "=" * 40)
    if success:
        print("✅ YouTube download test passed!")
        print("🎉 The WhatsApp bot YouTube download functionality is working correctly with cookies.")
    else:
        print("❌ YouTube download test failed!")
        print("⚠️  Please check the errors above.")

if __name__ == "__main__":
    asyncio.run(main())