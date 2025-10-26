#!/usr/bin/env python3
"""
Test script to verify download functionality for various platforms
"""
import os
import sys
import asyncio
import shutil
from pathlib import Path
from typing import Dict, Any, Optional

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the download functions from whatsapp_bot
from whatsapp_bot import (
    download_media, 
    download_media_with_filename,
    process_spotify_url,
    download_instagram_media,
    extract_direct_media_url,
    get_media_info,
    detect_platform,
    ensure_directories,
    cleanup_file
)

# Test URLs
TEST_URLS = [
    "https://www.youtube.com/shorts/4H-ckF9H_y0",  # YouTube shorts
    "https://www.instagram.com/reel/DLP0StQz1Tq/",  # Instagram reels
    "https://www.instagram.com/p/DGDfJ3LzdEL/",     # Instagram reels
    "https://www.instagram.com/p/DJeuZqsz5JT/",     # Instagram post
    "https://www.instagram.com/p/DK_2g5CzKwQ/?img_index=1",  # Instagram carousel post
    "https://vt.tiktok.com/ZSUKPdCtm",              # TikTok video
]

# Spotify test URL
SPOTIFY_URL = "https://open.spotify.com/track/5cmZe5DxE3uicDwfe24ls6?si=58d5dcb261584e62"

async def test_url_download(url: str, test_dir: str) -> bool:
    """Test downloading a single URL"""
    print(f"\n{'='*60}")
    print(f"Testing: {url}")
    print(f"{'='*60}")
    
    try:
        platform = detect_platform(url)
        print(f"Platform detected: {platform}")
        
        # Create a unique filename for this test
        filename = f"test_{platform}_{hash(url) % 10000}"
        
        # Test media info extraction
        print("Extracting media info...")
        info: Optional[Dict[Any, Any]] = await get_media_info(url)
        if info:
            print(f"Title: {info.get('title', 'Unknown')}")
            print(f"Uploader: {info.get('uploader', 'Unknown')}")
            print(f"Content type: {info.get('content_type', 'Unknown')}")
        else:
            print("Failed to extract media info")
            
        # Test download
        print("Downloading media...")
        file_path = await download_media(url, quality="best", audio_only=False, info=info or {})
        
        if file_path and os.path.exists(file_path):
            # Move file to test directory
            file_name = os.path.basename(file_path)
            destination = os.path.join(test_dir, f"{filename}_{file_name}")
            shutil.move(file_path, destination)
            print(f"✅ Download successful: {destination}")
            return True
        else:
            print("❌ Download failed")
            return False
            
    except Exception as e:
        print(f"❌ Error downloading {url}: {str(e)}")
        return False

async def test_spotify_download(test_dir: str) -> bool:
    """Test Spotify download"""
    print(f"\n{'='*60}")
    print(f"Testing Spotify: {SPOTIFY_URL}")
    print(f"{'='*60}")
    
    try:
        print("Processing Spotify URL...")
        spotify_metadata = await process_spotify_url(SPOTIFY_URL)
        if not spotify_metadata:
            print("❌ Failed to process Spotify URL")
            return False
            
        print(f"Track: {spotify_metadata.get('full_title', 'Unknown')}")
        
        print("Downloading Spotify track as MP3...")
        file_path = await download_media_with_filename(
            spotify_metadata['search_query'], 
            filename=spotify_metadata['filename'],
            audio_only=True
        )
        
        if file_path and os.path.exists(file_path):
            # Move file to test directory
            file_name = os.path.basename(file_path)
            destination = os.path.join(test_dir, f"spotify_{file_name}")
            shutil.move(file_path, destination)
            print(f"✅ Spotify download successful: {destination}")
            return True
        else:
            print("❌ Spotify download failed")
            return False
            
    except Exception as e:
        print(f"❌ Error downloading Spotify track: {str(e)}")
        return False

async def test_instagram_direct_download(url: str, test_dir: str) -> bool:
    """Test Instagram direct download method"""
    print(f"\n{'='*60}")
    print(f"Testing Instagram direct download: {url}")
    print(f"{'='*60}")
    
    try:
        print("Attempting direct Instagram download...")
        instagram_data = await download_instagram_media(url)
        
        if instagram_data and instagram_data.get('media_files'):
            print(f"✅ Instagram download successful: {len(instagram_data['media_files'])} files")
            
            # Move files to test directory
            for i, media_file in enumerate(instagram_data['media_files']):
                src_path = media_file['path']
                if os.path.exists(src_path):
                    file_ext = os.path.splitext(src_path)[1]
                    dest_path = os.path.join(test_dir, f"instagram_direct_{i}_{hash(url) % 10000}{file_ext}")
                    shutil.move(src_path, dest_path)
                    print(f"  - Saved: {os.path.basename(dest_path)}")
            
            # Clean up temp directory
            if 'temp_dir' in instagram_data and os.path.exists(instagram_data['temp_dir']):
                shutil.rmtree(instagram_data['temp_dir'], ignore_errors=True)
            
            return True
        else:
            print("❌ Instagram direct download failed")
            return False
            
    except Exception as e:
        print(f"❌ Error in Instagram direct download: {str(e)}")
        return False

async def main():
    """Main test function"""
    print("🚀 Starting WhatsApp Bot Download Tests")
    print("=" * 60)
    
    # Ensure directories exist
    ensure_directories()
    
    # Create test directory
    test_dir = "test_downloads"
    os.makedirs(test_dir, exist_ok=True)
    print(f"Test downloads will be saved to: {test_dir}")
    
    # Test results
    results = []
    
    # Test each URL
    for url in TEST_URLS:
        try:
            success = await test_url_download(url, test_dir)
            results.append((url, success))
        except Exception as e:
            print(f"❌ Failed to test {url}: {str(e)}")
            results.append((url, False))
        # Add delay between tests
        await asyncio.sleep(2)
    
    # Test Spotify
    try:
        success = await test_spotify_download(test_dir)
        results.append(("Spotify Track", success))
    except Exception as e:
        print(f"❌ Failed to test Spotify: {str(e)}")
        results.append(("Spotify Track", False))
    
    # Test Instagram direct download for one URL
    instagram_url = "https://www.instagram.com/p/DJeuZqsz5JT/"
    try:
        success = await test_instagram_direct_download(instagram_url, test_dir)
        results.append((f"Instagram Direct ({instagram_url})", success))
    except Exception as e:
        print(f"❌ Failed to test Instagram direct download: {str(e)}")
        results.append((f"Instagram Direct ({instagram_url})", False))
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for url, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {url}")
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📈 Total: {len(results)} | Passed: {passed} | Failed: {failed}")
    
    if failed == 0:
        print("🎉 All tests passed! The WhatsApp bot should work correctly.")
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        
    print(f"\n📁 Downloaded files are in the '{test_dir}' directory")

if __name__ == "__main__":
    asyncio.run(main())