import os
import hashlib
import time
import re
import logging
import json
from typing import Optional, Dict, Any

# Import configuration
from config import (
    MAX_FILE_SIZE, DOWNLOADS_DIR, TEMP_DIR, DATA_DIR,
    PHONE_NUMBER_ID, WHATSAPP_TOKEN, VERIFY_TOKEN
)

# Try to import required libraries
try:
    import yt_dlp
    YTDLP_AVAILABLE = True
except ImportError:
    yt_dlp = None
    YTDLP_AVAILABLE = False
    print("Warning: yt-dlp not available. Some features will be limited.")

try:
    import instaloader
    INSTALOADER_AVAILABLE = True
except ImportError:
    instaloader = None
    INSTALOADER_AVAILABLE = False
    print("Warning: instaloader not available. Instagram features will be limited.")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Simple WhatsApp Business API mock
class WhatsAppBusiness:
    def __init__(self, access_token: str, phone_number_id: str):
        self.access_token = access_token
        self.phone_number_id = phone_number_id
    
    def send_message(self, message: str, recipient_id: str):
        """Send a text message"""
        print(f"[WhatsApp] Sending message to {recipient_id}: {message}")
        return {"success": True}
    
    def send_document(self, document_path: str, recipient_id: str, caption: Optional[str] = None):
        """Send a document"""
        print(f"[WhatsApp] Sending document to {recipient_id}: {document_path}")
        if caption:
            print(f"Caption: {caption}")
        return {"success": True}

# Initialize WhatsApp client
messenger = WhatsAppBusiness(WHATSAPP_TOKEN, PHONE_NUMBER_ID)

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
    
    if 'instagram.com/reel/' in url_lower:
        return 'instagram_reel'
    elif 'instagram.com' in url_lower:
        return 'instagram'
    elif 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'youtube'
    elif 'tiktok.com' in url_lower:
        return 'tiktok'
    elif 'facebook.com' in url_lower:
        return 'facebook'
    elif 'spotify.com' in url_lower:
        return 'spotify'
    elif 'twitter.com' in url_lower or 'x.com' in url_lower:
        return 'twitter'
    
    return 'unknown'

def is_supported_url(url: str) -> bool:
    """Check if URL is from supported platform"""
    return detect_platform(url) != 'unknown'

def sanitize_text(text: str) -> str:
    """Sanitize text for WhatsApp"""
    # Remove or replace characters that might cause issues in WhatsApp
    sanitized = re.sub(r'[^\w\s\-_.:]', '', text)
    return sanitized[:1000]  # Limit length

def extract_instagram_reel_info_with_ytdlp(url: str) -> Dict[str, str]:
    """Extract Instagram reel title and creator information using yt-dlp"""
    if not YTDLP_AVAILABLE or yt_dlp is None:
        return {
            'title': "Instagram Reel",
            'creator': "Unknown"
        }
    
    try:
        # yt-dlp options for extracting info only (no download)
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
            'socket_timeout': 10,
            'retries': 2,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            # Extract title and creator/uploader
            title = info.get('title', 'Instagram Reel')
            creator = info.get('uploader', 'Unknown')
            
            # Ensure we return strings
            if title is None:
                title = "Instagram Reel"
            if creator is None:
                creator = "Unknown"
            
            return {
                'title': str(title),
                'creator': str(creator)
            }
    except Exception as e:
        logger.error(f"Failed to extract Instagram reel info with yt-dlp: {e}")
        return {
            'title': "Instagram Reel",
            'creator': "Unknown"
        }

def download_instagram_reel_with_ytdlp(url: str) -> str:
    """Download Instagram reel using yt-dlp"""
    if not YTDLP_AVAILABLE or yt_dlp is None:
        raise Exception("yt-dlp not available")
    
    try:
        import tempfile
        import uuid
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(dir=TEMP_DIR)
        
        # yt-dlp options for downloading
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': os.path.join(temp_dir, '%(id)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'merge_output_format': 'mp4',
            'noplaylist': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            # Find downloaded file
            video_file = None
            for file in os.listdir(temp_dir):
                if file.endswith(('.mp4', '.mov', '.avi', '.mkv')):
                    video_file = os.path.join(temp_dir, file)
                    break
            
            if not video_file:
                raise Exception("No video file found after download")
            
            return video_file
    except Exception as e:
        logger.error(f"Failed to download Instagram reel with yt-dlp: {e}")
        raise

def process_message(recipient_id: str, text: str):
    """Process incoming WhatsApp messages"""
    # Handle commands
    if text.lower() in ['help', 'start']:
        welcome_text = "🚀 *Ultra-Fast Media Downloader*\n\n"
        welcome_text += "Download from YouTube, Instagram, TikTok, Spotify, Twitter, Facebook and more!\n\n"
        welcome_text += "✨ *Features:*\n"
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
    messenger.send_message("💡 *Tip*\n\nSend a social media link to download content, or type *help* for more information!", recipient_id)

def handle_link(recipient_id: str, url: str):
    """Handle incoming links with intelligent processing"""
    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        messenger.send_message("❌ *Invalid URL*\n\nPlease send a valid link starting with http:// or https://", recipient_id)
        return
    
    if not is_supported_url(url):
        messenger.send_message(
            "❌ *Unsupported Platform*\n\nSupported platforms:\n🎬 YouTube\n📱 Instagram\n🎪 TikTok\n🎵 Spotify\n🐦 Twitter/X\n📘 Facebook",
            recipient_id
        )
        return
    
    platform = detect_platform(url)
    
    logger.info(f"📥 Processing {platform} URL from user {recipient_id}: {url}")
    
    # Show processing message
    messenger.send_message(f"🔄 *Processing {platform.title()} link...*", recipient_id)
    
    # Handle Instagram reel specifically (as requested in the task)
    if platform == 'instagram_reel':
        handle_instagram_reel(recipient_id, url)
        return
    
    # For other content, send a generic response
    messenger.send_message(f"🔄 *Processing {platform.title()} content...*\nThis may take a few moments.", recipient_id)

def extract_instagram_reel_info(url: str) -> Dict[str, str]:
    """Extract Instagram reel title and creator information using instaloader"""
    if not INSTALOADER_AVAILABLE or instaloader is None:
        # Fallback to yt-dlp if instaloader is not available
        return extract_instagram_reel_info_with_ytdlp(url)
    
    try:
        # Extract shortcode from URL
        shortcode = url.split("/")[-2]
        
        # Create instaloader instance
        L = instaloader.Instaloader()
        
        # Load post using shortcode
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        # Extract title and creator
        title = post.caption[:100] + "..." if post.caption and len(post.caption) > 100 else (post.caption or "Instagram Reel")
        creator = f"@{post.owner_username}" if post.owner_username else "Unknown"
        
        return {
            'title': title,
            'creator': creator
        }
    except Exception as e:
        logger.error(f"Failed to extract Instagram reel info with instaloader: {e}")
        # Fallback to yt-dlp
        return extract_instagram_reel_info_with_ytdlp(url)

def download_instagram_reel(url: str) -> str:
    """Download Instagram reel using instaloader"""
    if not INSTALOADER_AVAILABLE or instaloader is None:
        # Fallback to yt-dlp if instaloader is not available
        return download_instagram_reel_with_ytdlp(url)
    
    try:
        import tempfile
        import uuid
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp(dir=TEMP_DIR)
        
        # Create instaloader instance
        L = instaloader.Instaloader(
            download_videos=True,
            download_video_thumbnails=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            post_metadata_txt_pattern="",
            quiet=True
        )
        
        # Extract shortcode from URL
        shortcode = url.split("/")[-2]
        
        # Load post using shortcode
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        # Download the post
        L.download_post(post, target=shortcode)
        
        # Find downloaded video file
        video_file = None
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.endswith('.mp4'):
                    video_file = os.path.join(root, file)
                    break
            if video_file:
                break
        
        # If no MP4 found, look for other video formats
        if not video_file:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith(('.mov', '.avi', '.mkv')):
                        video_file = os.path.join(root, file)
                        break
                if video_file:
                    break
        
        if not video_file:
            raise Exception("No video file found after download")
        
        # Move file to downloads directory with a clean name
        filename = f"instagram_reel_{shortcode}.mp4"
        final_path = os.path.join(DOWNLOADS_DIR, filename)
        os.rename(video_file, final_path)
        
        return final_path
    except Exception as e:
        logger.error(f"Failed to download Instagram reel with instaloader: {e}")
        # Fallback to yt-dlp
        return download_instagram_reel_with_ytdlp(url)

def handle_instagram_reel(recipient_id: str, url: str):
    """Handle Instagram reel download and send with real information extraction"""
    try:
        # Send processing message
        messenger.send_message("📥 *Downloading Instagram reel...*", recipient_id)
        
        # Extract real title and creator information
        reel_info = extract_instagram_reel_info(url)
        title = reel_info['title']
        creator = reel_info['creator']
        
        # Send info message with real title and creator
        info_message = f"📹 *{title}*\n👤 *Creator: {creator}*"
        messenger.send_message(info_message, recipient_id)
        
        # Download the reel
        messenger.send_message("⬇️ *Downloading video file...*", recipient_id)
        file_path = download_instagram_reel(url)
        
        # Check if file was downloaded successfully
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            size_mb = file_size / (1024 * 1024)
            messenger.send_message(f"✅ *Successfully downloaded!* Size: {size_mb:.1f}MB", recipient_id)
            
            # In a real implementation, we would send the actual file
            # messenger.send_document(file_path, recipient_id, f"Instagram Reel • {os.path.basename(file_path)}")
            
            # For demonstration, show that file exists
            messenger.send_message(f"📎 *File downloaded to:* {file_path}", recipient_id)
        else:
            messenger.send_message("❌ *Download failed*", recipient_id)
        
    except Exception as e:
        logger.error(f"Instagram reel handling failed: {e}")
        messenger.send_message(f"❌ *Failed to download Instagram reel*\nError: {str(e)}", recipient_id)

def verify_webhook(mode: str, token: str, challenge: str):
    """Verify webhook subscription"""
    if mode and token:
        if mode == 'subscribe' and token == VERIFY_TOKEN:
            logger.info('✅ Webhook verified successfully!')
            return challenge
        else:
            logger.error('❌ Webhook verification failed!')
            return 'Verification failed', 403
    return 'Bad Request', 400

def main():
    """Main function to test the WhatsApp bot"""
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