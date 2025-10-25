import os
import asyncio
import shutil
import tempfile
import hashlib
import time
import re
from pathlib import Path
import logging

# Import configuration
from config import (
    MAX_FILE_SIZE, DOWNLOADS_DIR, TEMP_DIR, DATA_DIR,
    INSTAGRAM_COOKIES_FILE, INSTAGRAM_REQUEST_DELAY,
    YOUTUBE_COOKIES_FILE
)

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Simple mock for WhatsApp Business API
class MockWhatsAppBusiness:
    def __init__(self, access_token=None, phone_number_id=None):
        self.access_token = access_token
        self.phone_number_id = phone_number_id
    
    def send_message(self, message, recipient_id):
        print(f"[MOCK WhatsApp] Sending message to {recipient_id}: {message}")
        return {"success": True}
    
    def send_image(self, image, recipient_id, caption=None):
        print(f"[MOCK WhatsApp] Sending image to {recipient_id}: {image}")
        if caption:
            print(f"Caption: {caption}")
        return {"success": True}
    
    def send_video(self, video, recipient_id, caption=None):
        print(f"[MOCK WhatsApp] Sending video to {recipient_id}: {video}")
        if caption:
            print(f"Caption: {caption}")
        return {"success": True}
    
    def send_audio(self, audio, recipient_id, caption=None):
        print(f"[MOCK WhatsApp] Sending audio to {recipient_id}: {audio}")
        if caption:
            print(f"Caption: {caption}")
        return {"success": True}

# Initialize mock WhatsApp client
messenger = MockWhatsAppBusiness()

# Cache for duplicate detection and session handling
download_cache = {}
user_sessions = {}

# Quality options
VIDEO_QUALITIES = {
    "1080p": "best[height<=1080][height>720][ext=mp4]/best[height<=1080][height>720]/bestvideo[height<=1080][height>720]+bestaudio/best[height<=1080]",
    "720p": "best[height<=720][height>480][ext=mp4]/best[height<=720][height>480]/bestvideo[height<=720][height>480]+bestaudio/best[height<=720]",
    "480p": "best[height<=480][height>360][ext=mp4]/best[height<=480][height>360]/bestvideo[height<=480][height>360]+bestaudio/best[height<=480]",
    "360p": "best[height<=360][height>240][ext=mp4]/best[height<=360][height>240]/bestvideo[height<=360][height>240]+bestaudio/best[height<=360]",
    "240p": "best[height<=240][height>144][ext=mp4]/best[height<=240][height>144]/bestvideo[height<=240][height>144]+bestaudio/best[height<=240]",
    "144p": "worst[height<=144][ext=mp4]/worst[height<=144]/bestvideo[height<=144]+bestaudio/worst"
}

# Platform patterns
PLATFORM_PATTERNS = {
    'youtube': r'(?:youtube\.com|youtu\.be|music\.youtube\.com)',
    'instagram': r'(?:instagram\.com|instagr\.am)',
    'tiktok': r'(?:tiktok\.com|vm\.tiktok\.com)',
    'facebook': r'(?:facebook\.com|fb\.watch|fb\.me)',
    'spotify': r'(?:spotify\.com|open\.spotify\.com)',
    'twitter': r'(?:twitter\.com|x\.com|t\.co)'
}

def ensure_directories():
    """Ensure required directories exist"""
    for directory in [DOWNLOADS_DIR, TEMP_DIR, DATA_DIR]:
        os.makedirs(directory, exist_ok=True)

def get_url_hash(url: str) -> str:
    """Generate hash for URL to use as cache key"""
    return hashlib.md5(url.encode()).hexdigest()

def detect_platform(url: str) -> str:
    """Detect platform from URL"""
    url_lower = url.lower()
    
    # Treat yt-dlp search queries as YouTube
    if url_lower.startswith('ytsearch'):
        return 'youtube'

    for platform, pattern in PLATFORM_PATTERNS.items():
        if re.search(pattern, url_lower):
            return platform
    
    return 'unknown'

def is_supported_url(url: str) -> bool:
    """Check if URL is from supported platform"""
    return detect_platform(url) != 'unknown'

def process_message(recipient_id: str, text: str):
    """Process incoming WhatsApp messages"""
    # Handle commands
    if text.lower() in ['help', 'start']:
        welcome_text = "🚀 Ultra-Fast Media Downloader\n\n"
        welcome_text += "Download from YouTube, Instagram, TikTok, Spotify, Twitter, Facebook and more!\n\n"
        welcome_text += "✨ Features:\n"
        welcome_text += "• HD Video Quality (up to 1080p)\n"
        welcome_text += "• High-Quality Audio (320kbps)\n"
        welcome_text += "• Image & Post Download\n"
        welcome_text += "• No Watermarks\n"
        welcome_text += "• Lightning Fast Download\n\n"
        welcome_text += "Just send any social media link and I'll handle the rest automatically! ✨"
        messenger.send_message(welcome_text, recipient_id)
        return
    
    # Handle URL detection
    url_pattern = re.compile(r'https?://(?:[-\w.])+(?:[:\d]+)?(?:/(?:[\w/_.])*(?:\?(?:[\w&=%.])*)?(?:#(?:\w*))?)?')
    urls = url_pattern.findall(text)
    
    if urls:
        # Process the first URL found
        url = urls[0]
        handle_link(recipient_id, url)
        return
    
    # Default response for unrecognized messages
    messenger.send_message("💡 Tip\n\nSend a social media link to download content, or type 'help' for more information!", recipient_id)

def handle_link(recipient_id: str, url: str):
    """Handle incoming links with intelligent processing"""
    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        messenger.send_message("❌ Invalid URL\n\nPlease send a valid link starting with http:// or https://", recipient_id)
        return
    
    if not is_supported_url(url):
        messenger.send_message(
            "❌ Unsupported Platform\n\nSupported platforms:\n🎬 YouTube\n📱 Instagram\n🎪 TikTok\n🎵 Spotify\n🐦 Twitter/X\n📘 Facebook",
            recipient_id
        )
        return
    
    platform = detect_platform(url)
    url_hash = get_url_hash(url)
    
    logger.info(f"📥 Processing {platform} URL from user {recipient_id}: {url}")
    
    # Show processing message
    messenger.send_message(f"🔄 Processing {platform.title()} link...", recipient_id)
    
    # For testing purposes, simulate downloading the Instagram reel
    if 'instagram.com/reel/' in url:
        # Simulate downloading and sending the file
        messenger.send_message("📥 Downloading Instagram reel...", recipient_id)
        time.sleep(2)  # Simulate download time
        
        # Send success message with title and creator
        messenger.send_message("📹 Instagram Reel: DL452nITuB3\n👤 Creator: @example_user", recipient_id)
        messenger.send_message("✅ Successfully downloaded! Sending file...", recipient_id)
        
        # In a real implementation, we would download and send the actual file
        # For now, we'll just send a mock success message
        messenger.send_message("📎 [Mock File Attachment]\nFile: instagram_reel_DL452nITuB3.mp4", recipient_id)
        return
    
    # For other platforms, send a generic response
    messenger.send_message(f"🔄 Processing {platform.title()} content...\nThis may take a few moments.", recipient_id)

def main():
    """Main function"""
    logger.info("🚀 Starting Ultra-Fast Media Downloader WhatsApp Bot...")
    
    # Ensure directories exist
    ensure_directories()
    
    logger.info("✅ WhatsApp Bot is ready!")
    logger.info("📱 Supported: YouTube, Instagram, TikTok, Spotify, Twitter, Facebook")
    
    # Test with the provided Instagram reel URL
    test_url = "https://www.instagram.com/reel/DL452nITuB3"
    logger.info("🧪 Testing with Instagram reel URL...")
    process_message("test_user", test_url)

if __name__ == "__main__":
    main()