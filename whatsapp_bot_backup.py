import os
import asyncio
import aiohttp
import aiofiles
import subprocess
import shutil
import tempfile
import hashlib
import time
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List, Any, Tuple
import logging
from urllib.parse import urlparse, parse_qs
import mimetypes

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

import yt_dlp
import requests
from bs4 import BeautifulSoup
import instaloader
import uuid
import qrcode
from PIL import Image, ImageDraw, ImageFont

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import configuration from .env
from dotenv import load_dotenv
load_dotenv()

# WhatsApp API Configuration
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
YOUTUBE_CHANNEL_ID = os.getenv("YOUTUBE_CHANNEL_ID")

# Proxy Settings (optional - for Instagram requests)
PROXY_HOST = os.getenv('PROXY_HOST', '')
PROXY_PORT = os.getenv('PROXY_PORT', '')
PROXY_USER = os.getenv('PROXY_USER', '')
PROXY_PASS = os.getenv('PROXY_PASS', '')

# Instagram Settings
INSTAGRAM_COOKIES_FILE = "cookies.txt"  # Path to Instagram cookies file (Netscape format)
INSTAGRAM_REQUEST_DELAY = 4  # Delay between Instagram requests (seconds) - increased to reduce 403 errors

# YouTube Settings
# Path to YouTube cookies file (Netscape format)
YOUTUBE_COOKIES_FILE = "ytcookies.txt"

# File Size Limits
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB in bytes (WhatsApp limit)

# Directory Settings
DOWNLOADS_DIR = "downloads"
TEMP_DIR = "temp"
DATA_DIR = "data"  # For storing persistent data like last video ID

class InstagramCookieManager:
    """Manages Instagram cookies for authentication and proxy support"""
    
    def __init__(self, cookies_file: str = INSTAGRAM_COOKIES_FILE):
        self.cookies_file = cookies_file
        self.cookies = {}
        self.session_cookies = None
        self.proxy_config = None
        self.last_request_time = 0
        self._setup_proxy()
        self._load_cookies()
    
    def _setup_proxy(self):
        """Setup proxy configuration if provided"""
        # Check if proxy environment variables are set and not empty
        if PROXY_HOST and PROXY_PORT and PROXY_HOST.strip() and PROXY_PORT.strip():
            try:
                proxy_url = f"http://{PROXY_HOST}:{PROXY_PORT}"
                if PROXY_USER and PROXY_PASS and PROXY_USER.strip() and PROXY_PASS.strip():
                    proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
                
                self.proxy_config = {
                    'http': proxy_url,
                    'https': proxy_url
                }
                logger.info(f"✅ Proxy configured: {PROXY_HOST}:{PROXY_PORT}")
            except Exception as e:
                logger.warning(f"❌ Proxy configuration failed: {e}")
                self.proxy_config = None
        else:
            # Skip proxy configuration gracefully when environment variables are empty
            self.proxy_config = None
            logger.info("ℹ️ No proxy configuration found, using direct connection")
    
    def _load_cookies(self):
        """Load cookies from Netscape format cookies.txt file"""
        try:
            if not os.path.exists(self.cookies_file):
                logger.warning(f"❌ Instagram cookies file not found: {self.cookies_file}")
                logger.warning("⚠️ Instagram downloads may fail without proper authentication cookies")
                return
            
            # Parse Netscape format cookies.txt
            self.cookies = {}
            with open(self.cookies_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines, but not HttpOnly cookies
                    if not line or (line.startswith('#') and not line.startswith('#HttpOnly_')):
                        continue
                    
                    # Remove #HttpOnly_ prefix if present (Netscape format for HttpOnly cookies)
                    if line.startswith('#HttpOnly_'):
                        line = line[10:]  # Remove '#HttpOnly_' prefix
                    
                    # Parse Netscape format: domain, flag, path, secure, expiration, name, value
                    parts = line.split('\t')
                    if len(parts) >= 7:
                        domain = parts[0]
                        name = parts[5]
                        value = parts[6]
                        
                        # Only load Instagram cookies
                        if '.instagram.com' in domain:
                            self.cookies[name] = value
            
            # Create session cookies for requests
            self.session_cookies = requests.cookies.RequestsCookieJar()
            for name, value in self.cookies.items():
                self.session_cookies.set(name, value, domain='.instagram.com')
            
            logger.info(f"✅ Loaded {len(self.cookies)} Instagram cookies from Netscape format")
            
            # Enhanced cookie validation
            self._validate_loaded_cookies()
            
        except Exception as e:
            logger.error(f"❌ Failed to load Instagram cookies: {e}")
            self.cookies = {}
            self.session_cookies = None
    
    def _validate_loaded_cookies(self):
        """Validate loaded cookies and provide detailed warnings"""
        # Log important cookies for debugging (without values for security)
        important_cookies = ['sessionid', 'ds_user_id', 'csrftoken', 'mid', 'datr']
        found_cookies = [name for name in important_cookies if name in self.cookies]
        missing_cookies = [name for name in important_cookies if name not in self.cookies]
        
        logger.info(f"🔑 Authentication cookies found: {', '.join(found_cookies)}")
        
        if missing_cookies:
            logger.warning(f"⚠️ Missing cookies: {', '.join(missing_cookies)}")
        
        # Critical validation checks
        if 'sessionid' not in self.cookies:
            logger.error("❌ CRITICAL: sessionid cookie is missing!")
            logger.error("⚠️ Instagram downloads will likely fail without a valid sessionid")
            logger.error("📝 Please update your cookies.txt file with a fresh sessionid from your browser")
            return False
        
        if 'ds_user_id' not in self.cookies:
            logger.warning("⚠️ WARNING: ds_user_id cookie is missing - this may cause authentication issues")
        
        # Check if sessionid looks valid (basic format check)
        sessionid = self.cookies.get('sessionid', '')
        if sessionid:
            # Instagram sessionid typically contains URL-encoded user ID followed by session data
            if '%3A' in sessionid or ':' in sessionid:
                logger.info("✅ sessionid format appears valid")
                
                # Extract user ID from sessionid for additional validation
                try:
                    if '%3A' in sessionid:
                        user_id_from_session = sessionid.split('%3A')[0]
                    else:
                        user_id_from_session = sessionid.split(':')[0]
                    
                    ds_user_id = self.cookies.get('ds_user_id', '')
                    if ds_user_id and user_id_from_session == ds_user_id:
                        logger.info("✅ sessionid and ds_user_id are consistent")
                    elif ds_user_id:
                        logger.warning("⚠️ sessionid and ds_user_id do not match - cookies may be inconsistent")
                        
                except Exception as e:
                    logger.debug(f"Could not validate sessionid format: {e}")
            else:
                logger.warning("⚠️ sessionid format looks unusual - authentication may fail")
        
        return True
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers for Instagram requests with proper authentication"""
        headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0'
        }
        
        # Add CSRF token if available
        if 'csrftoken' in self.cookies:
            headers['X-CSRFToken'] = self.cookies['csrftoken']
        
        return headers
    
    async def rate_limit(self):
        """Implement rate limiting for Instagram requests"""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        
        if time_since_last < INSTAGRAM_REQUEST_DELAY:
            sleep_time = INSTAGRAM_REQUEST_DELAY - time_since_last
            logger.debug(f"⏱️ Rate limiting: sleeping {sleep_time:.1f}s")
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def get_instaloader_session(self):
        """Configure instaloader with cookies"""
        try:
            # Create a new instaloader instance
            loader = instaloader.Instaloader(
                download_videos=True,
                download_video_thumbnails=False,
                download_comments=False,
                save_metadata=False,
                compress_json=False,
                post_metadata_txt_pattern="",
                quiet=True  # Reduce logging noise
            )
            
            # Load session from cookies if available
            if self.session_cookies and 'sessionid' in self.cookies:
                try:
                    # Import session from cookies
                    session_id = self.cookies['sessionid']
                    user_id = self.cookies.get('ds_user_id', '')
                    
                    if session_id and user_id:
                        # Create session file temporarily
                        session_file = f"{TEMP_DIR}/instagram_session"
                        os.makedirs(TEMP_DIR, exist_ok=True)
                        
                        # Load session using instaloader's method
                        loader.context._session.cookies.update(self.session_cookies)
                        logger.info("✅ Instagram session loaded with cookies")
                        
                except Exception as e:
                    logger.warning(f"⚠️ Could not load Instagram session: {e}")
            
            return loader
            
        except Exception as e:
            logger.error(f"❌ Failed to create Instagram loader: {e}")
            return None
    
    def is_authenticated(self) -> bool:
        """Check if we have valid authentication cookies"""
        return bool(self.cookies and 'sessionid' in self.cookies and 'ds_user_id' in self.cookies)
    
    async def validate_cookies(self) -> bool:
        """Validate cookies by making a test request to Instagram"""
        if not self.is_authenticated():
            logger.warning("⚠️ No authentication cookies available for validation")
            return False
        
        try:
            await self.rate_limit()
            
            # Test request to Instagram API endpoint
            test_url = "https://www.instagram.com/accounts/edit/"
            headers = self.get_headers()
            
            # Use proxy if available
            proxies = self.proxy_config if self.proxy_config else None
            
            response = requests.get(test_url, headers=headers, cookies=self.session_cookies, 
                                  proxies=proxies, timeout=10, allow_redirects=False)
            
            if response.status_code == 200:
                logger.info("✅ Instagram cookies validation successful")
                return True
            elif response.status_code == 302:
                # Redirect might indicate login required
                if 'login' in response.headers.get('Location', '').lower():
                    logger.warning("⚠️ Instagram cookies appear to be expired (redirected to login)")
                    return False
                else:
                    logger.info("✅ Instagram cookies validation successful (redirect)")
                    return True
            elif response.status_code == 403:
                logger.warning("⚠️ Instagram access forbidden - cookies may be invalid or rate limited")
                return False
            else:
                logger.warning(f"⚠️ Instagram cookies validation returned status: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ Instagram cookies validation failed: {e}")
            return False
    
    def get_ytdl_opts(self, base_opts: Dict = None) -> Dict:
        """Get yt-dlp options with Instagram authentication and proxy support"""
        opts = base_opts.copy() if base_opts else {}
        
        # Add Instagram cookies from Netscape format cookies.txt file
        if os.path.exists(self.cookies_file):
            # Use cookiefile option for Netscape format cookies.txt
            opts['cookiefile'] = self.cookies_file
            logger.info(f"🍪 Using Netscape cookies file: {self.cookies_file}")
            
            # Validate that we have essential cookies loaded
            if self.cookies and 'sessionid' in self.cookies:
                logger.info("🔑 Instagram authentication cookies detected for yt-dlp")
            else:
                logger.warning("⚠️ No sessionid found in cookies - Instagram access may be limited")
        
        # Add proxy if available
        if self.proxy_config:
            opts['proxy'] = self.proxy_config.get('https', self.proxy_config.get('http'))
            logger.info(f"🌐 Using proxy for yt-dlp: {opts['proxy']}")
        elif PROXY_HOST and PROXY_PORT:
            # Handle empty proxy environment variables gracefully
            if PROXY_HOST.strip() and PROXY_PORT.strip():
                proxy_url = f"http://{PROXY_HOST}:{PROXY_PORT}"
                if PROXY_USER and PROXY_PASS and PROXY_USER.strip() and PROXY_PASS.strip():
                    proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
                opts['proxy'] = proxy_url
                logger.info(f"🌐 Using proxy for yt-dlp: {proxy_url}")
        
        # Add Instagram-specific headers (without cookies)
        opts['http_headers'] = opts.get('http_headers', {})
        instagram_headers = self.get_headers()
        # Remove Cookie header since we're using cookiefile instead
        
        # Add error handling for expired cookies
        def error_hook(d):
            if d['status'] == 'error':
                error_msg = str(d.get('error', '')).lower()
                if 'login' in error_msg or 'unauthorized' in error_msg or '401' in error_msg:
                    logger.error("🔒 Instagram authentication failed - cookies may be expired")
                elif '403' in error_msg or 'forbidden' in error_msg:
                    logger.error("🚫 Instagram access forbidden - possible rate limiting or invalid cookies")
                elif 'private' in error_msg:
                    logger.error("🔒 Instagram content is private - authentication may be required")
        
        opts['progress_hooks'] = opts.get('progress_hooks', [])
        opts['progress_hooks'].append(error_hook)
        instagram_headers.pop('Cookie', None)
        opts['http_headers'].update(instagram_headers)
        
        return opts

# Initialize Instagram cookie manager
instagram_auth = InstagramCookieManager()

# Validate cookies on startup (async function will be called later)
async def validate_instagram_setup():
    """Comprehensive Instagram setup validation on startup"""
    logger.info("🔍 Validating Instagram configuration...")
    
    # Check if cookies file exists
    if not os.path.exists(INSTAGRAM_COOKIES_FILE):
        logger.error(f"❌ Instagram cookies file not found: {INSTAGRAM_COOKIES_FILE}")
        logger.error("📝 Please create a cookies.txt file with your Instagram session cookies")
        logger.error("💡 You can extract cookies using browser extensions like 'Cookie-Editor'")
        return False
    
    # Check basic authentication
    if not instagram_auth.is_authenticated():
        logger.error("❌ Instagram authentication failed - missing sessionid or ds_user_id")
        logger.error("⚠️ Instagram downloads will likely fail")
        logger.error("📝 Please ensure your cookies.txt contains valid sessionid and ds_user_id cookies")
        return False
    
    # Test cookie validity with actual Instagram request
    logger.info("🔍 Testing Instagram cookies with live validation...")
    try:
        is_valid = await instagram_auth.validate_cookies()
        if is_valid:
            logger.info("✅ Instagram authentication is working properly")
            logger.info("🎯 Instagram downloads should work correctly")
            return True
        else:
            logger.error("❌ Instagram cookies validation failed")
            logger.error("⚠️ Your cookies may be expired or invalid")
            logger.error("📝 Please update your cookies.txt with fresh cookies from your browser")
            logger.error("💡 Make sure you're logged into Instagram in your browser when extracting cookies")
            return False
    except Exception as e:
        logger.error(f"❌ Instagram validation error: {e}")
        logger.warning("⚠️ Could not validate Instagram setup - downloads may fail")
        return False

async def validate_youtube_setup():
    """Validate YouTube cookies setup on startup"""
    logger.info("🔍 Validating YouTube configuration...")
    
    # Check if YouTube cookies file exists
    if not os.path.exists(YOUTUBE_COOKIES_FILE):
        logger.warning(f"⚠️ YouTube cookies file not found: {YOUTUBE_COOKIES_FILE}")
        logger.warning("📝 YouTube downloads may be rate-limited without cookies")
        logger.warning("💡 Create a ytcookies.txt file with your YouTube session cookies for better reliability")
        return False
    
    # Try to load and validate YouTube cookies
    try:
        # Check if file has content
        if os.path.getsize(YOUTUBE_COOKIES_FILE) == 0:
            logger.warning(f"⚠️ YouTube cookies file is empty: {YOUTUBE_COOKIES_FILE}")
            return False
            
        # Try to read the cookies file
        with open(YOUTUBE_COOKIES_FILE, 'r') as f:
            content = f.read()
            if not content.strip():
                logger.warning(f"⚠️ YouTube cookies file is empty: {YOUTUBE_COOKIES_FILE}")
                return False
                
        logger.info(f"✅ YouTube cookies file loaded: {YOUTUBE_COOKIES_FILE}")
        logger.info("🎯 YouTube downloads should work with authentication")
        return True
        
    except Exception as e:
        logger.error(f"❌ YouTube cookies validation failed: {e}")
        logger.warning("⚠️ YouTube downloads may fail without valid cookies")
        return False

# Instaloader setup with authentication
instagram_loader = instagram_auth.get_instaloader_session() or instaloader.Instaloader(
    download_videos=True,
    download_video_thumbnails=False,
    download_comments=False,
    save_metadata=False,
    compress_json=False,
    post_metadata_txt_pattern="",
    quiet=True
)

# Cache for duplicate detection and session handling
download_cache: Dict[str, Dict] = {}
user_sessions: Dict[str, Dict] = {}  # Using phone number as key instead of user ID

# Quality options with strict resolution constraints
VIDEO_QUALITIES = {
    "1080p": "best[height<=1080][height>720][ext=mp4]/best[height<=1080][height>720]/bestvideo[height<=1080][height>720]+bestaudio/best[height<=1080]",
    "720p": "best[height<=720][height>480][ext=mp4]/best[height<=720][height>480]/bestvideo[height<=720][height>480]+bestaudio/best[height<=720]",
    "480p": "best[height<=480][height>360][ext=mp4]/best[height<=480][height>360]/bestvideo[height<=480][height>360]+bestaudio/best[height<=480]",
    "360p": "best[height<=360][height>240][ext=mp4]/best[height<=360][height>240]/bestvideo[height<=360][height>240]+bestaudio/best[height<=360]",
    "240p": "best[height<=240][height>144][ext=mp4]/best[height<=240][height>144]/bestvideo[height<=240][height>144]+bestaudio/best[height<=240]",
    "144p": "worst[height<=144][ext=mp4]/worst[height<=144]/bestvideo[height<=144]+bestaudio/worst"
}

# Platform patterns with enhanced detection (ordered by specificity)
PLATFORM_PATTERNS = {
    'youtube': r'(?:youtube\.com|youtu\.be|music\.youtube\.com)',
    'pinterest': r'(?:pinterest\.com|pin\.it)',
    'instagram': r'(?:instagram\.com|instagr\.am)',
    'threads': r'(?:threads\.net)',
    'tiktok': r'(?:tiktok\.com|vm\.tiktok\.com)',
    'facebook': r'(?:facebook\.com|fb\.watch|fb\.me)',
    'spotify': r'(?:spotify\.com|open\.spotify\.com)',
    'twitter': r'(?:twitter\.com|x\.com|t\.co)'
}

# Image file extensions
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg'}

# User agents for different platforms
USER_AGENTS = {
    'default': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'pinterest': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'instagram': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
    'facebook': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
    'tiktok': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def ensure_directories():
    """Ensure required directories exist"""
    for directory in [DOWNLOADS_DIR, TEMP_DIR, DATA_DIR]:
        os.makedirs(directory, exist_ok=True)

def get_url_hash(url: str) -> str:
    """Generate hash for URL to use as cache key"""
    return hashlib.md5(url.encode()).hexdigest()

def sanitize_filename(title: str, max_length: int = 100) -> str:
    """Sanitize title for use as filename by removing invalid characters and handling Unicode"""
    if not title or not title.strip():
        return f"audio_{int(time.time())}"
    
    # Handle Unicode characters by normalizing and encoding/decoding
    try:
        import unicodedata
        # Normalize Unicode characters (convert accented characters to ASCII equivalents)
        safe_title = unicodedata.normalize('NFKD', title)
        safe_title = safe_title.encode('ascii', 'ignore').decode('ascii')
    except:
        safe_title = title
    
    # Remove invalid filename characters
    safe_title = re.sub(r'[<>:"/\\|?*]', '', safe_title)
    # Remove consecutive dots and whitespace
    safe_title = re.sub(r'\.{2,}', '.', safe_title)
    safe_title = re.sub(r'\s+', ' ', safe_title).strip()
    
    # Remove leading/trailing dots and spaces
    safe_title = safe_title.strip('. ')
    
    # Replace problematic characters with safe alternatives
    safe_title = safe_title.replace('&', 'and')
    safe_title = safe_title.replace('#', 'no')
    safe_title = safe_title.replace('%', 'percent')
    safe_title = safe_title.replace('(', '')
    safe_title = safe_title.replace(')', '')
    safe_title = safe_title.replace('[', '')
    safe_title = safe_title.replace(']', '')
    
    # Remove any remaining non-ASCII characters that might cause issues
    safe_title = re.sub(r'[^\w\s\-_.]', '', safe_title)
    
    # Limit length and break at word boundary if possible
    if len(safe_title) > max_length:
        truncated = safe_title[:max_length]
        # Try to break at word boundary
        last_space = truncated.rfind(' ')
        if last_space > max_length * 0.7:  # Only break at word if we don't lose too much
            safe_title = truncated[:last_space]
        else:
            safe_title = truncated
    
    # Final cleanup - remove trailing punctuation and whitespace
    safe_title = safe_title.rstrip('.,!?;:-_ ')
    
    # Fallback if title becomes empty after sanitization
    if not safe_title or safe_title.isspace() or len(safe_title) < 3:
        safe_title = f"audio_{int(time.time())}"
    
    logger.debug(f"🎵 Sanitized filename: '{title}' -> '{safe_title}'")
    return safe_title

def detect_platform(url: str) -> Optional[str]:
    """Detect platform from URL with enhanced logging"""
    url_lower = url.lower()
    logger.debug(f"🔍 Platform detection for URL: {url}")
    
    # Treat yt-dlp search queries (ytsearch, ytsearch1, etc.) as YouTube
    if url_lower.startswith('ytsearch'):
        logger.info(f"🎯 Detected platform: youtube for URL: {url}")
        return 'youtube'

    for platform, pattern in PLATFORM_PATTERNS.items():
        if re.search(pattern, url_lower):
            logger.info(f"🎯 Detected platform: {platform} for URL: {url}")
            return platform
    
    logger.warning(f"❓ Unknown platform for URL: {url}")
    return None

def is_supported_url(url: str) -> bool:
    """Check if URL is from supported platform"""
    return detect_platform(url) is not None

def detect_content_type(url: str, info: Dict = None) -> str:
    """Enhanced content type detection with better image detection"""
    url_lower = url.lower()
    
    # Check URL patterns for direct image links
    if any(ext in url_lower for ext in IMAGE_EXTENSIONS):
        return 'image'
    
    # Check for common image hosting patterns
    image_domains = ['imgur.com', 'i.redd.it', 'pbs.twimg.com', 'scontent', 'cdninstagram', 'pinimg.com']
    if any(domain in url_lower for domain in image_domains):
        return 'image'
    
    # Platform-specific detection
    if 'instagram.com' in url_lower:
        if '/p/' in url_lower:  # Instagram post (could be image or video)
            return 'mixed'  # Will be determined by yt-dlp or fallback
        elif '/reel/' in url_lower or '/reels/' in url_lower:
            return 'video'
        elif '/stories/' in url_lower:
            return 'mixed'
    
    if 'threads.net' in url_lower:
        # Threads posts can contain images or videos, similar to Instagram
        return 'mixed'  # Will be determined by yt-dlp or fallback
    
    if 'pinterest.com' in url_lower or 'pin.it' in url_lower:
        # Pinterest can have both images and videos
        return 'mixed'  # Will be determined by content extraction
    
    if 'facebook.com' in url_lower:
        if 'photo.php' in url_lower or '/photos/' in url_lower:
            return 'image'
        elif 'video.php' in url_lower or '/videos/' in url_lower:
            return 'video'
        else:
            return 'mixed'  # Mixed content post
    
    if 'twitter.com' in url_lower or 'x.com' in url_lower:
        if '/photo/' in url_lower:
            return 'image'
        elif '/video/' in url_lower:
            return 'video'
        else:
            return 'mixed'  # Tweet with media
    
    # If we have yt-dlp info, use it
    if info:
        formats = info.get('formats', [])
        has_video = any(f.get('vcodec', 'none') != 'none' for f in formats)
        has_audio = any(f.get('acodec', 'none') != 'none' for f in formats)
        
        if has_video:
            return 'video'
        elif has_audio:
            return 'audio'
        else:
            return 'image'
    
    # Default to mixed for unknown content (will try auto-detection)
    return 'mixed'

async def extract_direct_media_url(url: str, platform: str) -> Optional[Dict]:
    """Extract direct media URLs using custom scrapers"""
    try:
        headers = {
            'User-Agent': USER_AGENTS.get(platform, USER_AGENTS['default']),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        }
        
        if platform == 'pinterest':
            return await extract_pinterest_media(url, headers)
        elif platform == 'instagram':
            return await extract_instagram_media_fallback(url, headers)
        elif platform == 'threads':
            # Threads uses the same extraction logic as Instagram
            logger.info("🧵 Extracting Threads media using Instagram fallback method")
            return await extract_instagram_media_fallback(url, headers)
        elif platform == 'facebook':
            return await extract_facebook_media(url, headers)
        
        return None
    except Exception as e:
        logger.error(f"Direct extraction failed for {platform}: {e}")
        return None

async def extract_pinterest_media(url: str, headers: Dict) -> Optional[Dict]:
    """Extract Pinterest media URLs with enhanced video detection"""
    try:
        # Ensure we have the full Pinterest URL
        if 'pin.it' in url:
            # Resolve short URL first
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(url, allow_redirects=True) as response:
                    url = str(response.url)
        
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Method 1: Look for JSON data in script tags (most reliable)
                scripts = soup.find_all('script', string=re.compile(r'pinData|__PWS_DATA__'))
                for script in scripts:
                    script_content = script.string
                    if not script_content:
                        continue
                    
                    # Try different JSON patterns
                    patterns = [
                        r'pinData\s*=\s*({.*?});',
                        r'__PWS_DATA__\s*=\s*({.*?});',
                        r'bootstrapData\s*=\s*({.*?});'
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, script_content, re.DOTALL)
                        if match:
                            try:
                                pin_data = json.loads(match.group(1))
                                result = extract_pinterest_urls_from_data(pin_data)
                                if result:
                                    return result
                            except Exception as e:
                                logger.debug(f"JSON parsing failed: {e}")
                                continue
                
                # Method 2: Look for video tags and sources
                video_tag = soup.find('video')
                if video_tag:
                    source_tag = video_tag.find('source')
                    if source_tag and source_tag.get('src'):
                        return {
                            'type': 'video',
                            'url': source_tag['src'],
                            'title': soup.find('meta', property='og:title', content=True).get('content', 'Pinterest Video') if soup.find('meta', property='og:title') else 'Pinterest Video'
                        }
                
                # Method 3: Look for meta tags
                og_video = soup.find('meta', property='og:video')
                og_video_url = soup.find('meta', property='og:video:url')
                og_image = soup.find('meta', property='og:image')
                
                if og_video and og_video.get('content'):
                    return {
                        'type': 'video',
                        'url': og_video['content'],
                        'title': soup.find('meta', property='og:title', content=True).get('content', 'Pinterest Video') if soup.find('meta', property='og:title') else 'Pinterest Video'
                    }
                elif og_video_url and og_video_url.get('content'):
                    return {
                        'type': 'video',
                        'url': og_video_url['content'],
                        'title': soup.find('meta', property='og:title', content=True).get('content', 'Pinterest Video') if soup.find('meta', property='og:title') else 'Pinterest Video'
                    }
                elif og_image and og_image.get('content'):
                    # Get the highest quality image
                    image_url = og_image['content']
                    # Try to get original quality by modifying URL
                    if '236x' in image_url:
                        image_url = image_url.replace('236x', 'originals')
                    elif '474x' in image_url:
                        image_url = image_url.replace('474x', 'originals')
                    
                    return {
                        'type': 'image',
                        'url': image_url,
                        'title': soup.find('meta', property='og:title', content=True).get('content', 'Pinterest Image') if soup.find('meta', property='og:title') else 'Pinterest Image'
                    }
                
                # Method 4: Look for data attributes
                pin_containers = soup.find_all(['div', 'section'], {'data-test-id': re.compile(r'pin|story')})
                for container in pin_containers:
                    img_tags = container.find_all('img')
                    for img in img_tags:
                        if img.get('src') and 'pinimg.com' in img.get('src', ''):
                            return {
                                'type': 'image',
                                'url': img['src'],
                                'title': img.get('alt', 'Pinterest Image')
                            }
        
        return None
    except Exception as e:
        logger.error(f"Pinterest extraction error: {e}")
        return None

def extract_pinterest_urls_from_data(pin_data: Dict) -> Optional[Dict]:
    """Extract URLs from Pinterest pin data"""
    try:
        # Look for video URLs
        videos = pin_data.get('videos', {})
        if videos:
            video_list = videos.get('video_list', {})
            if video_list:
                # Get the best quality video
                best_video = None
                for quality in ['V_EXP7', 'V_EXP6', 'V_EXP5', 'V_EXP4', 'V_720P', 'V_HLSV4', 'V_HLSV3']:
                    if quality in video_list:
                        best_video = video_list[quality]
                        break
                
                if best_video and best_video.get('url'):
                    return {
                        'type': 'video',
                        'url': best_video['url'],
                        'title': pin_data.get('title', 'Pinterest Video')
                    }
        
        # Look for images
        images = pin_data.get('images', {})
        if images:
            orig_image = images.get('orig')
            if orig_image and orig_image.get('url'):
                return {
                    'type': 'image',
                    'url': orig_image['url'],
                    'title': pin_data.get('title', 'Pinterest Image')
                }
        
        return None
    except Exception as e:
        logger.error(f"Pinterest data extraction error: {e}")
        return None

def extract_instagram_shortcode(url: str) -> str | None:
    """Extract Instagram shortcode from URL"""
    try:
        parts = url.strip('/').split('/')
        if 'p' in parts:
            return parts[parts.index('p') + 1]
        elif 'reel' in parts:
            return parts[parts.index('reel') + 1]
        elif 'tv' in parts:
            return parts[parts.index('tv') + 1]
        elif 'stories' in parts:
            # For stories, we might need different handling
            return None  # Stories are more complex to handle
    except Exception as e:
        logger.error(f"Shortcode extraction error: {e}")
        return None

async def download_instagram_media(url: str) -> Optional[Dict]:
    """Download Instagram media using authenticated instaloader"""
    try:
        # Apply rate limiting
        await instagram_auth.rate_limit()
        
        shortcode = extract_instagram_shortcode(url)
        if not shortcode:
            logger.error("Could not extract shortcode from Instagram URL")
            return None

        # Create temporary directory
        temp_dir = f"{TEMP_DIR}/instagram_{uuid.uuid4().hex}"
        os.makedirs(temp_dir, exist_ok=True)
        
        # Use authenticated loader or create new one
        loader = instagram_auth.get_instaloader_session() or instagram_loader
        loader.dirname_pattern = temp_dir

        try:
            logger.info(f"🔄 Downloading Instagram post with shortcode: {shortcode}")
            
            # Check if we have authentication
            if instagram_auth.is_authenticated():
                logger.info("🔑 Using authenticated Instagram session")
            else:
                logger.warning("⚠️ No Instagram authentication - may fail on private/restricted content")
            
            # Get post from shortcode
            post = instaloader.Post.from_shortcode(loader.context, shortcode)
            
            # Download the post
            loader.download_post(post, target=shortcode)
            
            # Collect downloaded files
            media_files = []
            for root, _, files in os.walk(temp_dir):
                for file in sorted(files):
                    full_path = os.path.join(root, file)
                    if file.endswith((".jpg", ".jpeg", ".png", ".mp4", ".webp")):
                        media_files.append({
                            'path': full_path,
                            'type': 'video' if file.endswith('.mp4') else 'image',
                            'filename': file
                        })
            
            if not media_files:
                logger.error("No media files found after download")
                return None
            
            logger.info(f"✅ Downloaded {len(media_files)} Instagram media file(s)")
            
            return {
                'media_files': media_files,
                'temp_dir': temp_dir,
                'title': post.caption[:100] + "..." if post.caption and len(post.caption) > 100 else (post.caption or "Instagram Post"),
                'owner': post.owner_username,
                'is_video': post.is_video,
                'is_carousel': len(media_files) > 1,
                'media_count': len(media_files)
            }
            
        except Exception as e:
            logger.error(f"Instaloader download error: {e}")
            # Clean up temp directory
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            return None
            
    except Exception as e:
        logger.error(f"Instagram download error: {e}")
        return None

async def send_instagram_media_group(phone_number: str, media_data: Dict, processing_msg_id: str = None):
    """Send Instagram media as group (for carousel posts) or single media"""
    try:
        media_files = media_data['media_files']
        title = media_data['title']
        
        if len(media_files) == 1:
            # Single media
            file_path = media_files[0]['path']
            media_type = media_files[0]['type']
            
            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE:
                await send_text_message(phone_number, "❌ File too large (max 50MB)")
                return
            
            # Send the media file
            try:
                size_mb = file_size / (1024 * 1024)
                caption = f"📷 {title}\n\n✅ Instagram {media_type.title()} • {size_mb:.1f}MB"
                
                if media_type == 'image':
                    await send_image_message(phone_number, file_path, caption)
                else:
                    await send_video_message(phone_number, file_path, caption)
                
            except Exception as e:
                logger.error(f"Send single media error: {e}")
                await send_text_message(phone_number, "❌ Failed to send media")
        
        else:
            # Multiple media (carousel) - send as a group with clear indication
            await send_text_message(phone_number, f"🔄 Sending carousel post with {len(media_files)} media items...")
            
            # Send a header message to indicate start of carousel
            header_caption = f"📷 Instagram Carousel Post: {title}\n\nSending {len(media_files)} media items..."
            await send_text_message(phone_number, header_caption)
            
            # Send each media item with a delay and clear numbering
            for i, media_file in enumerate(media_files[:10]):  # WhatsApp limit: 10 media
                file_path = media_file['path']
                media_type = media_file['type']
                
                file_size = os.path.getsize(file_path)
                if file_size > MAX_FILE_SIZE:
                    await send_text_message(phone_number, f"❌ Media {i+1} too large (max 50MB)")
                    continue
                
                try:
                    size_mb = file_size / (1024 * 1024)
                    # Include item number and total count in caption
                    caption = f"📱 Media {i+1}/{len(media_files)}\n\n📷 {title}\n\n✅ Instagram {media_type.title()} • {size_mb:.1f}MB"
                    
                    if media_type == 'image':
                        await send_image_message(phone_number, file_path, caption)
                    else:
                        await send_video_message(phone_number, file_path, caption)
                    
                    # Small delay between sending media to avoid rate limiting
                    await asyncio.sleep(1)
                        
                except Exception as e:
                    logger.error(f"Error sending media {i}: {e}")
                    await send_text_message(phone_number, f"❌ Failed to send media {i+1}")
            
            # Send a footer message to indicate end of carousel
            await send_text_message(phone_number, f"✅ Carousel post sending completed. Total: {len(media_files)} media items.")
    
    except Exception as e:
        logger.error(f"Instagram media send error: {e}")
        await send_text_message(phone_number, "❌ Failed to process media")
    
    finally:
        # Clean up temp directory
        if 'temp_dir' in media_data and os.path.exists(media_data['temp_dir']):
            shutil.rmtree(media_data['temp_dir'], ignore_errors=True)

async def detect_instagram_post_type(url: str) -> Optional[Dict]:
    """Detect Instagram post type (image/video/carousel) before attempting download"""
    try:
        # Apply rate limiting
        await instagram_auth.rate_limit()
        
        # Use authenticated headers
        auth_headers = instagram_auth.get_headers()
        
        # Try to extract basic post info
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(
            headers=auth_headers,
            timeout=timeout,
            cookies=instagram_auth.session_cookies
        ) as session:
            
            # Set proxy if available
            proxy = None
            if instagram_auth.proxy_config:
                proxy = instagram_auth.proxy_config.get('https')
            
            # Retry logic for 403 errors
            for attempt in range(3):
                try:
                    async with session.get(url, proxy=proxy) as response:
                        if response.status == 403:
                            if attempt < 2:
                                logger.debug(f"🔄 Instagram 403 retry {attempt + 1}/3")
                                await asyncio.sleep(1 + attempt)  # Small delay
                                continue
                            else:
                                logger.warning("🚫 Instagram 403 - access forbidden after retries")
                                return None
                        
                        if response.status != 200:
                            logger.debug(f"Instagram post type detection: HTTP {response.status}")
                            return None
                        
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Look for meta tags to determine post type
                        og_video = soup.find('meta', property='og:video')
                        og_image = soup.find('meta', property='og:image')
                        og_title = soup.find('meta', property='og:title')
                        og_description = soup.find('meta', property='og:description')
                        
                        # Check for carousel indicators
                        carousel_indicators = soup.find_all('meta', property='og:image')
                        is_carousel = len(carousel_indicators) > 1
                        
                        title = "Instagram Post"
                        if og_title and og_title.get('content'):
                            title = og_title['content']
                        elif og_description and og_description.get('content'):
                            title = og_description['content'][:100]
                        
                        if og_video and og_video.get('content'):
                            return {
                                'type': 'video',
                                'has_video': True,
                                'is_carousel': is_carousel,
                                'title': title,
                                'should_use_fallback': False
                            }
                        elif og_image and og_image.get('content'):
                            return {
                                'type': 'image',
                                'has_video': False,
                                'is_carousel': is_carousel,
                                'title': title,
                                'should_use_fallback': True  # Images should skip yt-dlp
                            }
                        
                        break  # Success, exit retry loop
                        
                except aiohttp.ClientError as e:
                    if attempt < 2:
                        logger.debug(f"🔄 Instagram connection retry {attempt + 1}/3: {e}")
                        await asyncio.sleep(1 + attempt)
                        continue
                    else:
                        logger.debug(f"Instagram post type detection failed after retries: {e}")
                        return None
        
        return None
    except Exception as e:
        logger.debug(f"Instagram post type detection error: {e}")
        return None

async def extract_instagram_media_fallback(url: str, headers: Dict = None) -> Optional[Dict]:
    """Enhanced Instagram fallback extraction with authentication and proxy support"""
    try:
        # Apply rate limiting
        await instagram_auth.rate_limit()
        
        # Use authenticated headers if available
        auth_headers = instagram_auth.get_headers()
        if headers:
            auth_headers.update(headers)
        
        # Configure session with proxy support
        connector_kwargs = {}
        if instagram_auth.proxy_config:
            logger.info("🌐 Using proxy for Instagram fallback extraction")
        
        # Try direct extraction with authentication
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(
            headers=auth_headers,
            timeout=timeout,
            cookies=instagram_auth.session_cookies
        ) as session:
            
            # Set proxy if available
            proxy = None
            if instagram_auth.proxy_config:
                proxy = instagram_auth.proxy_config.get('https')
            
            # Retry logic for 403 errors
            for attempt in range(3):
                try:
                    async with session.get(url, proxy=proxy) as response:
                        if response.status == 403:
                            if attempt < 2:
                                logger.debug(f"🔄 Instagram fallback 403 retry {attempt + 1}/3")
                                await asyncio.sleep(1.5 + attempt)  # Small delay
                                continue
                            else:
                                logger.warning(f"Instagram fallback: HTTP 403 after retries")
                                return None
                        
                        if response.status != 200:
                            logger.warning(f"Instagram fallback: HTTP {response.status}")
                            return None
                        
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        # Look for multiple meta tags
                        og_video = soup.find('meta', property='og:video')
                        og_image = soup.find('meta', property='og:image')
                        og_title = soup.find('meta', property='og:title')
                        og_description = soup.find('meta', property='og:description')
                        
                        title = "Instagram Post"
                        if og_title and og_title.get('content'):
                            title = og_title['content']
                        elif og_description and og_description.get('content'):
                            title = og_description['content'][:100]
                        
                        if og_video and og_video.get('content'):
                            logger.info("📹 Found Instagram video via fallback method")
                            return {
                                'type': 'video',
                                'url': og_video['content'],
                                'title': title
                            }
                        elif og_image and og_image.get('content'):
                            logger.info("📸 Found Instagram image via fallback method")
                            return {
                                'type': 'image',
                                'url': og_image['content'],
                                'title': title
                            }
                        
                        break  # Success, exit retry loop
                        
                except aiohttp.ClientError as e:
                    if attempt < 2:
                        logger.debug(f"🔄 Instagram fallback connection retry {attempt + 1}/3: {e}")
                        await asyncio.sleep(1.5 + attempt)
                        continue
                    else:
                        logger.error(f"Instagram fallback extraction failed after retries: {e}")
                        return None
        
        return None
    except Exception as e:
        logger.error(f"Instagram fallback extraction error: {e}")
        return None

async def extract_facebook_media(url: str, headers: Dict) -> Optional[Dict]:
    """Extract Facebook media URLs"""
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Look for og:video or og:image
                og_video = soup.find('meta', property='og:video')
                og_image = soup.find('meta', property='og:image')
                
                if og_video and og_video.get('content'):
                    return {
                        'type': 'video',
                        'url': og_video['content'],
                        'title': 'Facebook Video'
                    }
                elif og_image and og_image.get('content'):
                    return {
                        'type': 'image',
                        'url': og_image['content'],
                        'title': 'Facebook Image'
                    }
        
        return None
    except Exception as e:
        logger.error(f"Facebook extraction error: {e}")
        return None

async def download_direct_media(url: str, platform: str = None) -> Optional[str]:
    """Download media directly using aiohttp"""
    try:
        headers = {
            'User-Agent': USER_AGENTS.get(platform, USER_AGENTS['default']),
            'Referer': url if platform != 'pinterest' else 'https://www.pinterest.com/',
        }
        
        temp_dir = tempfile.mkdtemp(dir=TEMP_DIR)
        
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                
                content_type = response.headers.get('content-type', '')
                file_ext = '.jpg'  # default
                
                if 'video' in content_type:
                    file_ext = '.mp4'
                elif 'image' in content_type:
                    if 'png' in content_type:
                        file_ext = '.png'
                    elif 'gif' in content_type:
                        file_ext = '.gif'
                    elif 'webp' in content_type:
                        file_ext = '.webp'
                
                filename = f"{get_url_hash(url)[:8]}_{int(time.time())}{file_ext}"
                file_path = os.path.join(temp_dir, filename)
                
                async with aiofiles.open(file_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(8192):
                        await f.write(chunk)
                
                return file_path
    
    except Exception as e:
        logger.error(f"Direct download failed: {e}")
        return None

async def get_media_info(url: str) -> Optional[Dict]:
    """Extract media information with fallback to direct extraction"""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
            'socket_timeout': 20,
            'retries': 2,
            'noplaylist': True
        }
        
        platform = detect_platform(url)
        # Use YouTube cookies if available to bypass bot checks/captcha
        try:
            if platform == 'youtube' and os.path.exists(YOUTUBE_COOKIES_FILE):
                ydl_opts['cookiefile'] = YOUTUBE_COOKIES_FILE
        except Exception:
            pass
        
        # Try yt-dlp first
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Download thumbnail
                thumbnail_path = None
                if info.get('thumbnail'):
                    try:
                        response = requests.get(info['thumbnail'], timeout=10)
                        if response.status_code == 200:
                            thumbnail_path = f"{TEMP_DIR}/{info.get('id', 'temp')}.jpg"
                            with open(thumbnail_path, 'wb') as f:
                                f.write(response.content)
                    except Exception as e:
                        logger.warning(f"Thumbnail download failed: {e}")
                
                content_type = detect_content_type(url, info)
                
                return {
                    'title': info.get('title', 'Unknown Title'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail'),
                    'local_thumbnail': thumbnail_path,
                    'uploader': info.get('uploader', 'Unknown'),
                    'id': info.get('id', ''),
                    'platform': platform,
                    'content_type': content_type,
                    'timestamp': time.time(),
                    'source': 'yt-dlp'
                }
        
        except Exception as ytdlp_error:
            logger.warning(f"yt-dlp failed: {ytdlp_error}")
            
            # Fallback to direct extraction for certain platforms
            if platform in ['pinterest', 'instagram', 'threads', 'facebook']:
                media_info = await extract_direct_media_url(url, platform)
                if media_info:
                    return {
                        'title': media_info.get('title', f'{platform.title()} Media'),
                        'duration': 0,
                        'thumbnail': None,
                        'local_thumbnail': None,
                        'uploader': platform.title(),
                        'id': get_url_hash(url)[:8],
                        'platform': platform,
                        'content_type': media_info['type'],
                        'timestamp': time.time(),
                        'source': 'direct',
                        'direct_url': media_info['url']
                    }
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to extract info: {e}")
        return None

# --- QR Code Generator Function ---
FONT_PATH = os.path.join(os.path.dirname(__file__), "ShadowHand.ttf")   # Font file in project root
FIXED_TEXT = "@abdifahadi"   # Fixed center text

async def generate_qr_with_text(data: str) -> str:
    """Generate QR code with embedded center text"""
    try:
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(data)   # User input data (link or text)
        qr.make(fit=True)
        img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGB")

        # High Resolution (upscale for quality)
        upscale = 6
        img_qr = img_qr.resize((img_qr.size[0] * upscale, img_qr.size[1] * upscale), Image.NEAREST)

        img_w, img_h = img_qr.size
        draw = ImageDraw.Draw(img_qr)

        # Auto adjust font size
        try:
            font = ImageFont.truetype(FONT_PATH, int(img_w * 0.12))  # Text size
        except:
            font = ImageFont.load_default()
            logger.warning("⚠️ ShadowHand.ttf font not found, using default font")

        text = FIXED_TEXT
        text_bbox = draw.textbbox((0, 0), text, font=font)
        text_w, text_h = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
        
        # Scale down font if text is too wide
        while text_w > img_w * 0.7:  # If text > 70% of QR width, make smaller
            font_size = int(font.size * 0.9) if hasattr(font, 'size') else max(8, int(img_w * 0.10))
            try:
                font = ImageFont.truetype(FONT_PATH, font_size)
            except:
                font = ImageFont.load_default()
                break
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_w, text_h = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]

        # Center Position
        x = (img_w - text_w) // 2
        y = (img_h - text_h) // 2

        # White background (padding) for readability
        padding = int(0.05 * text_h)
        draw.rectangle(
            [(x - padding, y - padding), (x + text_w + padding, y + text_h + padding)],
            fill="white"
        )

        # Draw Text
        draw.text((x, y), text, font=font, fill="black")

        # Final downscale for smoothness
        final_img = img_qr.resize((img_w // upscale, img_h // upscale), Image.LANCZOS)

        # Generate unique filename
        timestamp = int(time.time())
        file_path = f"{TEMP_DIR}/qr_output_{timestamp}.png"
        final_img.save(file_path)
        return file_path

    except Exception as e:
        logger.error(f"❌ QR generation failed: {e}")
        raise

async def process_spotify_url(url: str) -> Optional[Dict]:
    """Process Spotify URL and return a YouTube search query and filename.
    Supports: track, artist, album, playlist URLs.
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        url_lower = url.lower()

        # Normalize and fetch page
        response = requests.get(url, headers=headers, timeout=12)
        if response.status_code != 200:
            return None

        soup = BeautifulSoup(response.text, 'html.parser')
        title_tag = soup.find('meta', property='og:title')
        desc_tag = soup.find('meta', property='og:description')

        title_text = (title_tag.get('content') if title_tag else '') or ''
        desc_text = (desc_tag.get('content') if desc_tag else '') or ''

        artist = ""
        track_name = ""
        search_query = None
        filename = None
        full_title = None

        # Helpers
        def clean_text(text: str) -> str:
            t = re.sub(r'\s*\(.*?\)\s*', '', text or '').strip()
            t = re.sub(r'\s+', ' ', t)
            return t

        # Track: prefer "Track • Artist" or parse JSON-LD MusicRecording
        if '/track/' in url_lower:
            # Try title like "Track • Artist" or "Artist - Track"
            if ' • ' in title_text:
                track_name, artist = title_text.split(' • ', 1)
            elif ' - ' in title_text:
                temp_a, temp_t = title_text.split(' - ', 1)
                # Often appears as "Artist - Track"
                artist, track_name = temp_a, temp_t
            else:
                track_name = title_text

            # Fallback parse from JSON-LD
            if (not artist or not track_name):
                for script in soup.find_all('script', type='application/ld+json'):
                    try:
                        data = json.loads(script.string or '{}')
                        if data.get('@type') == 'MusicRecording':
                            track_name = track_name or data.get('name', '')
                            by_artist = data.get('byArtist')
                            if isinstance(by_artist, dict):
                                artist = artist or by_artist.get('name', '')
                            elif isinstance(by_artist, list) and by_artist:
                                artist = artist or by_artist[0].get('name', '')
                    except Exception:
                        continue

            artist = clean_text(artist)
            track_name = clean_text(track_name)

            if artist:
                search_query = f"ytsearch1:{track_name} {artist}"
                filename = f"{artist} - {track_name}"
                full_title = filename
            else:
                search_query = f"ytsearch1:{track_name}"
                filename = track_name or 'Spotify Track'
                full_title = filename

        # Artist: search best popular track by artist name
        elif '/artist/' in url_lower:
            artist = clean_text(title_text or desc_text.split(' · ')[0] if ' · ' in desc_text else title_text)
            if not artist:
                return None
            search_query = f"ytsearch1:best song {artist}"
            filename = f"{artist} - Best Of"
            full_title = filename

        # Album: try album title with artist from description
        elif '/album/' in url_lower:
            album_title = clean_text(title_text)
            possible_artist = desc_text.split(' · ')[0] if ' · ' in desc_text else ''
            artist = clean_text(possible_artist)
            if artist:
                search_query = f"ytsearch1:{album_title} {artist} full album"
                filename = f"{artist} - {album_title}"
                full_title = filename
            else:
                search_query = f"ytsearch1:{album_title} full album"
                filename = album_title
                full_title = filename

        # Playlist: use playlist title to search best compilation
        elif '/playlist/' in url_lower:
            pl_title = clean_text(title_text or 'Spotify Playlist')
            search_query = f"ytsearch1:{pl_title} playlist"
            filename = pl_title
            full_title = pl_title

        else:
            return None

        return {
            'search_query': search_query,
            'artist': artist or 'Unknown Artist',
            'track_name': track_name or 'Unknown Track',
            'filename': filename or 'Spotify Audio',
            'full_title': full_title or filename or 'Spotify Audio'
        }

    except Exception as e:
        logger.error(f"Spotify processing error: {e}")
        return None

async def download_media_with_filename(url: str, filename: str = None, quality: str = None, audio_only: bool = False, info: Dict = None) -> Optional[str]:
    """Download media with custom filename"""
    try:
        platform = detect_platform(url)
        
        # For direct URLs from custom extraction
        if info and info.get('source') == 'direct' and info.get('direct_url'):
            return await download_direct_media(info['direct_url'], platform)
        
        # Try yt-dlp download first
        temp_dir = tempfile.mkdtemp(dir=TEMP_DIR)
        
        # Use custom filename if provided, otherwise use hash
        if filename:
            # Sanitize filename for filesystem
            safe_filename = re.sub(r'[<>:"/\\|?*]', '', filename)
            safe_filename = safe_filename.replace('..', '')[:100]  # Limit length
            base_filename = safe_filename
        else:
            # For audio downloads, try to use the video title if available
            if audio_only:
                title = None
                # Try multiple sources for the title with enhanced logging
                if info:
                    if info.get('title'):
                        title = info['title']
                        logger.debug(f"🎵 Found title in info: '{title}'")
                    elif info.get('yt_dlp_info') and info['yt_dlp_info'].get('title'):
                        title = info['yt_dlp_info']['title']
                        logger.debug(f"🎵 Found title in yt_dlp_info: '{title}'")
                    else:
                        logger.debug(f"🎵 No title found in info object: {info}")
                else:
                    logger.debug("🎵 No info object provided for audio download")
                
                # Try to extract info if not provided and this is a supported platform
                if not title and platform:
                    logger.info(f"🎵 Attempting to extract title for {platform} URL: {url}")
                    try:
                        extracted_info = await get_media_info(url)
                        if extracted_info and extracted_info.get('title'):
                            title = extracted_info['title']
                            logger.info(f"🎵 Successfully extracted title: '{title}'")
                    except Exception as e:
                        logger.debug(f"🎵 Failed to extract info for filename: {e}")
                
                if title and title.strip():
                    base_filename = sanitize_filename(title)
                    logger.info(f"🎵 Generated audio filename from title: '{title}' -> '{base_filename}'")
                else:
                    base_filename = f"audio_{get_url_hash(url)[:8]}_{int(time.time())}"
                    logger.warning(f"🎵 No title available for {platform} URL, using fallback filename: {base_filename}")
            else:
                base_filename = f"{get_url_hash(url)[:8]}_{int(time.time())}"
        
        if audio_only:
            output_template = os.path.join(temp_dir, f"{base_filename}.%(ext)s")
            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'outtmpl': output_template,
                'extractaudio': True,
                'audioformat': 'mp3',
                'audioquality': '320K',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True
            }
            # Use YouTube cookies if available
            try:
                if platform == 'youtube' and os.path.exists(YOUTUBE_COOKIES_FILE):
                    ydl_opts['cookiefile'] = YOUTUBE_COOKIES_FILE
            except Exception:
                pass
        else:
            output_template = os.path.join(temp_dir, f"{base_filename}.%(ext)s")
            format_selector = VIDEO_QUALITIES.get(quality, 'best[ext=mp4]/best')
            
            ydl_opts = {
                'format': format_selector,
                'outtmpl': output_template,
                'quiet': True,
                'no_warnings': True,
                'merge_output_format': 'mp4',
                'noplaylist': True
            }
            # Use YouTube cookies if available
            try:
                if platform == 'youtube' and os.path.exists(YOUTUBE_COOKIES_FILE):
                    ydl_opts['cookiefile'] = YOUTUBE_COOKIES_FILE
            except Exception:
                pass
        
        # Enhanced yt-dlp settings for better performance
        ydl_opts.update({
            'retries': 2,  # Reduced from 3 to 2 for faster failure handling
            'fragment_retries': 2,  # Reduced from 3 to 2
            'socket_timeout': 20,  # Reduced from 30 to 20 seconds
            'http_chunk_size': 16777216,  # Increased to 16MB for better speed
            'concurrent_fragment_downloads': 6,  # Increased from 4 to 6 for faster downloads
            'ignoreerrors': False,  # We want to catch errors for fallback
            'geo_bypass': True,  # Enable geo bypass for better access
            'no_check_certificate': True  # Skip SSL verification for faster connection
        })
        
        # Platform-specific headers for yt-dlp
        if platform == 'pinterest':
            ydl_opts['http_headers'] = {
                'User-Agent': USER_AGENTS['pinterest'],
                'Referer': 'https://www.pinterest.com/'
            }
        elif platform == 'instagram':
            ydl_opts['http_headers'] = {
                'User-Agent': USER_AGENTS['instagram']
            }
        elif platform == 'threads':
            # Threads uses the same authentication as Instagram
            logger.info("🧵 Processing Threads video using Instagram authentication")
            ydl_opts['http_headers'] = {
                'User-Agent': USER_AGENTS.get('instagram', USER_AGENTS['default'])
            }
        elif platform == 'facebook':
            ydl_opts['http_headers'] = {
                'User-Agent': USER_AGENTS['facebook']
            }
        elif platform == 'tiktok':
            ydl_opts['http_headers'] = {
                'User-Agent': USER_AGENTS['tiktok'],
                'Referer': 'https://www.tiktok.com/'
            }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Find downloaded file
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path) and file.startswith(base_filename):
                    return file_path
            
        except Exception as ytdlp_error:
            logger.warning(f"yt-dlp download failed: {ytdlp_error}")
            
            # Enhanced fallback logic for different platforms
            return await attempt_fallback_download(url, platform, temp_dir, base_filename, audio_only)
        
        return None
        
    except Exception as e:
        logger.error(f"Download failed: {e}")
        error_str = str(e).lower()
        
        if any(term in error_str for term in ['drm', 'protected', 'copyright']):
            raise Exception("DRM_PROTECTED")
        elif any(term in error_str for term in ['private', 'unavailable', 'access denied']):
            raise Exception("ACCESS_DENIED")
        elif any(term in error_str for term in ['age restricted', 'age-restricted']):
            raise Exception("AGE_RESTRICTED")
        else:
            raise Exception("DOWNLOAD_FAILED")

async def download_media(url: str, quality: str = None, audio_only: bool = False, info: Dict = None) -> Optional[str]:
    """Download media with enhanced fallback mechanisms"""
    try:
        platform = detect_platform(url)
        
        # For direct URLs from custom extraction
        if info and info.get('source') == 'direct' and info.get('direct_url'):
            return await download_direct_media(info['direct_url'], platform)
        
        # For Instagram with yt_dlp_info, use enhanced extraction
        if platform == 'instagram' and info and info.get('yt_dlp_info'):
            # Use the already extracted info for better compatibility
            pass  # Continue with normal yt-dlp download using the URL
        
        # Try yt-dlp download first
        temp_dir = tempfile.mkdtemp(dir=TEMP_DIR)
        
        # For audio downloads, try to use the video title if available
        if audio_only:
            title = None
            # Try multiple sources for the title with enhanced logging
            if info:
                if info.get('title'):
                    title = info['title']
                    logger.debug(f"🎵 Found title in info: '{title}'")
                elif info.get('yt_dlp_info') and info['yt_dlp_info'].get('title'):
                    title = info['yt_dlp_info']['title']
                    logger.debug(f"🎵 Found title in yt_dlp_info: '{title}'")
                else:
                    logger.debug(f"🎵 No title found in info object: {info}")
            else:
                logger.debug("🎵 No info object provided for audio download")
            
            # Try to extract info if not provided and this is a supported platform
            if not title and platform:
                logger.info(f"🎵 Attempting to extract title for {platform} URL: {url}")
                try:
                    extracted_info = await get_media_info(url)
                    if extracted_info and extracted_info.get('title'):
                        title = extracted_info['title']
                        logger.info(f"🎵 Successfully extracted title: '{title}'")
                except Exception as e:
                    logger.debug(f"🎵 Failed to extract info for filename: {e}")
            
            if title and title.strip():
                filename = sanitize_filename(title)
                logger.info(f"🎵 Generated audio filename from title: '{title}' -> '{filename}'")
            else:
                filename = f"audio_{get_url_hash(url)[:8]}_{int(time.time())}"
                logger.warning(f"🎵 No title available for {platform} URL, using fallback filename: {filename}")
        else:
            filename = f"{get_url_hash(url)[:8]}_{int(time.time())}"
        
        if audio_only:
            output_template = os.path.join(temp_dir, f"{filename}.%(ext)s")
            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio/best',
                'outtmpl': output_template,
                'extractaudio': True,
                'audioformat': 'mp3',
                'audioquality': '320K',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }],
                'quiet': True,
                'no_warnings': True,
                'noplaylist': True
            }
            # Use YouTube cookies if available
            try:
                if platform == 'youtube' and os.path.exists(YOUTUBE_COOKIES_FILE):
                    ydl_opts['cookiefile'] = YOUTUBE_COOKIES_FILE
            except Exception:
                pass
        else:
            output_template = os.path.join(temp_dir, f"{filename}.%(ext)s")
            format_selector = VIDEO_QUALITIES.get(quality, 'best[ext=mp4]/best')
            
            ydl_opts = {
                'format': format_selector,
                'outtmpl': output_template,
                'quiet': True,
                'no_warnings': True,
                'merge_output_format': 'mp4',
                'noplaylist': True
            }
            # Use YouTube cookies if available
            try:
                if platform == 'youtube' and os.path.exists(YOUTUBE_COOKIES_FILE):
                    ydl_opts['cookiefile'] = YOUTUBE_COOKIES_FILE
            except Exception:
                pass
        
        # Enhanced yt-dlp settings for better performance
        ydl_opts.update({
            'retries': 2,  # Reduced from 3 to 2 for faster failure handling
            'fragment_retries': 2,  # Reduced from 3 to 2
            'socket_timeout': 20,  # Reduced from 30 to 20 seconds
            'http_chunk_size': 16777216,  # Increased to 16MB for better speed
            'concurrent_fragment_downloads': 6,  # Increased from 4 to 6 for faster downloads
            'ignoreerrors': False,  # We want to catch errors for fallback
            'geo_bypass': True,  # Enable geo bypass for better access
            'no_check_certificate': True  # Skip SSL verification for faster connection
        })
        
        # Platform-specific headers for yt-dlp
        if platform == 'pinterest':
            ydl_opts['http_headers'] = {
                'User-Agent': USER_AGENTS['pinterest'],
                'Referer': 'https://www.pinterest.com/'
            }
        elif platform == 'instagram':
            # Check if no_auth flag is set for fallback attempts
            if info and info.get('no_auth'):
                logger.info("⚠️ Using non-authenticated Instagram download (fallback mode)")
                ydl_opts['http_headers'] = {
                    'User-Agent': USER_AGENTS.get('instagram', USER_AGENTS['default'])
                }
            else:
                # Use authenticated Instagram options
                ydl_opts = instagram_auth.get_ytdl_opts(ydl_opts)
                logger.info("🔑 Using authenticated Instagram download")
        elif platform == 'threads':
            # Threads uses the same authentication as Instagram
            logger.info("🧵 Processing Threads video using Instagram authentication")
            # Check if no_auth flag is set for fallback attempts
            if info and info.get('no_auth'):
                logger.info("⚠️ Using non-authenticated Threads download (fallback mode)")
                ydl_opts['http_headers'] = {
                    'User-Agent': USER_AGENTS.get('instagram', USER_AGENTS['default'])
                }
            else:
                # Use authenticated Instagram options for Threads
                ydl_opts = instagram_auth.get_ytdl_opts(ydl_opts)
                logger.info("🔑 Using authenticated Threads download")
        elif platform == 'facebook':
            ydl_opts['http_headers'] = {
                'User-Agent': USER_AGENTS['facebook']
            }
        elif platform == 'tiktok':
            ydl_opts['http_headers'] = {
                'User-Agent': USER_AGENTS['tiktok'],
                'Referer': 'https://www.tiktok.com/'
            }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Find downloaded file
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path) and file.startswith(filename):
                    return file_path
            
        except Exception as ytdlp_error:
            error_str = str(ytdlp_error).lower()
            
            # For Instagram and Threads, handle specific errors more gracefully
            if platform in ['instagram', 'threads']:
                # Check for common image-only post errors that should use fallback silently
                if any(err in error_str for err in ['no video formats found', 'no formats found', 'unable to extract', 'private video']):
                    # Log internally but don't spam user with scary errors
                    logger.debug(f"{platform.title()} yt-dlp expected failure (likely image-only post): {ytdlp_error}")
                    # Go directly to fallback without showing error
                    return await attempt_fallback_download(url, platform, temp_dir, filename, audio_only, silent_fallback=True)
                else:
                    # For other platform errors, log normally
                    logger.warning(f"{platform.title()} yt-dlp download failed: {ytdlp_error}")
            else:
                # For non-Instagram platforms, log normally
                logger.warning(f"yt-dlp download failed: {ytdlp_error}")
            
            # Enhanced fallback logic for different platforms
            return await attempt_fallback_download(url, platform, temp_dir, filename, audio_only)
        
        return None
        
    except Exception as e:
        logger.error(f"Download failed: {e}")
        error_str = str(e).lower()
        
        if any(term in error_str for term in ['drm', 'protected', 'copyright']):
            raise Exception("DRM_PROTECTED")
        elif any(term in error_str for term in ['private', 'unavailable', 'access denied']):
            raise Exception("ACCESS_DENIED")
        elif any(term in error_str for term in ['age restricted', 'age-restricted']):
            raise Exception("AGE_RESTRICTED")
        else:
            raise Exception("DOWNLOAD_FAILED")

async def attempt_fallback_download(url: str, platform: str, temp_dir: str, filename: str, audio_only: bool = False, silent_fallback: bool = False) -> Optional[str]:
    """Attempt fallback download methods"""
    try:
        # Method 1: Try direct extraction for supported platforms
        if platform in ['pinterest', 'instagram', 'threads', 'facebook', 'twitter']:
            # For Instagram and Threads, try instaloader first as fallback
            if platform in ['instagram', 'threads']:
                try:
                    instagram_data = await download_instagram_media(url)
                    if instagram_data and instagram_data.get('media_files'):
                        # Log success based on silence mode
                        if not silent_fallback:
                            logger.info(f"✅ {platform.title()} fallback download successful")
                        else:
                            logger.debug(f"✅ {platform.title()} silent fallback download successful")
                        # Return first media file path for compatibility
                        return instagram_data['media_files'][0]['path']
                except Exception as e:
                    if not silent_fallback:
                        logger.debug(f"Instagram instaloader fallback failed: {e}")
                    else:
                        logger.debug(f"Instagram silent instaloader fallback failed: {e}")
            
            media_info = await extract_direct_media_url(url, platform)
            if media_info and media_info.get('url'):
                return await download_direct_media(media_info['url'], platform)
        
        # Method 2: For images, try to extract image URLs from page
        if platform in ['instagram', 'facebook', 'twitter']:
            image_url = await extract_image_from_page(url, platform)
            if image_url:
                return await download_direct_media(image_url, platform)
        
        # Method 3: Try different yt-dlp extractors
        extractors_to_try = []
        if platform == 'pinterest':
            extractors_to_try = ['pinterest', 'generic']
        elif platform == 'instagram':
            extractors_to_try = ['instagram', 'generic']
        elif platform == 'threads':
            extractors_to_try = ['instagram', 'generic']  # Threads uses Instagram extractor
        elif platform == 'facebook':
            extractors_to_try = ['facebook', 'generic']
        
        for extractor in extractors_to_try:
            try:
                ydl_opts = {
                    'format': 'best',
                    'outtmpl': os.path.join(temp_dir, f"{filename}_fallback.%(ext)s"),
                    'quiet': True,
                    'no_warnings': True,
                    'extractor': extractor,
                    'retries': 1,
                    'socket_timeout': 10
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])
                
                # Check if file was created
                for file in os.listdir(temp_dir):
                    if file.startswith(f"{filename}_fallback"):
                        return os.path.join(temp_dir, file)
                        
            except Exception as e:
                logger.debug(f"Extractor {extractor} failed: {e}")
                continue
        
        return None
        
    except Exception as e:
        logger.error(f"Fallback download failed: {e}")
        return None

async def extract_image_from_page(url: str, platform: str) -> Optional[str]:
    """Extract image URL directly from page HTML"""
    try:
        headers = {
            'User-Agent': USER_AGENTS.get(platform, USER_AGENTS['default'])
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                
                # Look for various image sources
                selectors = [
                    'meta[property="og:image"]',
                    'meta[name="twitter:image"]',
                    'meta[property="og:image:url"]',
                    'img[data-src*="scontent"]',  # Facebook/Instagram
                    'img[src*="twimg.com"]',      # Twitter
                    'img[src*="pinimg.com"]'      # Pinterest
                ]
                
                for selector in selectors:
                    element = soup.select_one(selector)
                    if element:
                        image_url = element.get('content') or element.get('src') or element.get('data-src')
                        if image_url and any(ext in image_url.lower() for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                            return image_url
                
                return None
                
    except Exception as e:
        logger.error(f"Image extraction failed: {e}")
        return None

def cleanup_file(file_path: str):
    """Clean up downloaded files"""
    try:
        if file_path and os.path.exists(file_path):
            if os.path.isfile(file_path):
                os.remove(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
    except Exception as e:
        logger.warning(f"Cleanup failed: {e}")

# WhatsApp API functions
async def send_text_message(phone_number: str, text: str):
    """Send text message via WhatsApp API"""
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "text",
        "text": {
            "body": text
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    logger.info(f"✅ Text message sent to {phone_number}")
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to send text message: {response.status} - {error_text}")
                    return None
    except Exception as e:
        logger.error(f"❌ Exception sending text message: {e}")
        return None

async def send_image_message(phone_number: str, image_path: str, caption: str = ""):
    """Send image message via WhatsApp API"""
    # First upload the media
    media_id = await upload_media(image_path, "image")
    if not media_id:
        await send_text_message(phone_number, "❌ Failed to upload image")
        return
    
    # Then send the message
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "image",
        "image": {
            "id": media_id,
            "caption": caption[:1024]  # WhatsApp caption limit
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    logger.info(f"✅ Image message sent to {phone_number}")
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to send image message: {response.status} - {error_text}")
                    return None
    except Exception as e:
        logger.error(f"❌ Exception sending image message: {e}")
        return None

async def send_video_message(phone_number: str, video_path: str, caption: str = ""):
    """Send video message via WhatsApp API"""
    # First upload the media
    media_id = await upload_media(video_path, "video")
    if not media_id:
        await send_text_message(phone_number, "❌ Failed to upload video")
        return
    
    # Then send the message
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "video",
        "video": {
            "id": media_id,
            "caption": caption[:1024]  # WhatsApp caption limit
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    logger.info(f"✅ Video message sent to {phone_number}")
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to send video message: {response.status} - {error_text}")
                    return None
    except Exception as e:
        logger.error(f"❌ Exception sending video message: {e}")
        return None

async def send_audio_message(phone_number: str, audio_path: str):
    """Send audio message via WhatsApp API"""
    # First upload the media
    media_id = await upload_media(audio_path, "audio")
    if not media_id:
        await send_text_message(phone_number, "❌ Failed to upload audio")
        return
    
    # Then send the message
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "audio",
        "audio": {
            "id": media_id
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    logger.info(f"✅ Audio message sent to {phone_number}")
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to send audio message: {response.status} - {error_text}")
                    return None
    except Exception as e:
        logger.error(f"❌ Exception sending audio message: {e}")
        return None

async def upload_media(file_path: str, media_type: str):
    """Upload media to WhatsApp and return media ID"""
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/media"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
    }
    
    # Determine content type
    mime_type = "application/octet-stream"
    if media_type == "image":
        if file_path.endswith(('.jpg', '.jpeg')):
            mime_type = "image/jpeg"
        elif file_path.endswith('.png'):
            mime_type = "image/png"
        else:
            mime_type = "image/jpeg"  # Default to JPEG
    elif media_type == "video":
        mime_type = "video/mp4"
    elif media_type == "audio":
        if file_path.endswith('.mp3'):
            mime_type = "audio/mpeg"
        else:
            mime_type = "audio/mp4"
    
    try:
        # Create proper multipart form data
        data = aiohttp.FormData()
        data.add_field('file', 
                      open(file_path, 'rb'), 
                      filename=os.path.basename(file_path), 
                      content_type=mime_type)
        data.add_field('type', media_type)
        data.add_field('messaging_product', 'whatsapp')
        
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=data) as response:
                if response.status == 200:
                    result = await response.json()
                    media_id = result.get('id')
                    logger.info(f"✅ Media uploaded successfully: {media_id}")
                    return media_id
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to upload media: {response.status} - {error_text}")
                    # Log additional debug info
                    logger.error(f"File path: {file_path}")
                    logger.error(f"Media type: {media_type}")
                    logger.error(f"Mime type: {mime_type}")
                    logger.error(f"File size: {os.path.getsize(file_path) if os.path.exists(file_path) else 'File not found'}")
                    return None
    except Exception as e:
        logger.error(f"❌ Exception uploading media: {e}")
        logger.error(f"File path: {file_path}")
        logger.error(f"Media type: {media_type}")
        return None

async def send_interactive_message(phone_number: str, header_text: str, body_text: str, button_texts: List[str]):
    """Send interactive message with buttons via WhatsApp API"""
    url = f"https://graph.facebook.com/v17.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    
    # Create buttons
    buttons = []
    for i, text in enumerate(button_texts[:3]):  # Max 3 buttons
        buttons.append({
            "type": "reply",
            "reply": {
                "id": f"button_{i+1}",
                "title": text[:20]  # Button title limit
            }
        })
    
    payload = {
        "messaging_product": "whatsapp",
        "to": phone_number,
        "type": "interactive",
        "interactive": {
            "type": "button",
            "header": {
                "type": "text",
                "text": header_text[:60]  # Header text limit
            },
            "body": {
                "text": body_text[:1024]  # Body text limit
            },
            "action": {
                "buttons": buttons
            }
        }
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload) as response:
                if response.status == 200:
                    logger.info(f"✅ Interactive message sent to {phone_number}")
                    return await response.json()
                else:
                    error_text = await response.text()
                    logger.error(f"❌ Failed to send interactive message: {response.status} - {error_text}")
                    return None
    except Exception as e:
        logger.error(f"❌ Exception sending interactive message: {e}")
        return None

# WhatsApp message handlers
async def handle_welcome_message(phone_number: str):
    """Send welcome message with options"""
    welcome_text = """🚀 Ultra-Fast Media Downloader

Download from YouTube, Instagram, TikTok, Spotify, Twitter, Facebook, Pinterest and more!

✨ Features:
• HD Video Quality (up to 1080p)
• High-Quality Audio (320kbps)
• Image & Post Download
• No Watermarks
• Lightning Fast Download
• Smart Content Detection
• Auto-Format Selection

Just send any link and I'll handle the rest automatically! ✨"""
    
    await send_text_message(phone_number, welcome_text)

async def handle_help_message(phone_number: str):
    """Send help message"""
    help_text = """📥 Send Your Link

Supported Platforms:
🎬 YouTube - Video & Audio (all qualities)
📱 Instagram - Reels, Posts, Stories & Images
🎵 Spotify - Music (Auto MP3 conversion)
🎪 TikTok - Videos without watermark
🐦 Twitter/X - Videos, GIFs & Images
📘 Facebook - Videos, Posts & Images
📌 Pinterest - Videos & Images

Just send any link and I'll handle the rest automatically! ✨"""
    
    await send_text_message(phone_number, help_text)

async def handle_qr_message(phone_number: str):
    """Send QR code generation instructions"""
    qr_text = """📲 QR Code Generator

Send me any text or link and I will generate a QR code for you.

✨ Features:
• High-quality QR codes
• Custom branding with @abdifahadi
• Professional design
• Instant generation

Just send your text or link now! 📱"""
    
    await send_text_message(phone_number, qr_text)

async def handle_link_message(phone_number: str, url: str):
    """Handle incoming links with intelligent processing"""
    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        await send_text_message(phone_number, "❌ Invalid URL\n\nPlease send a valid link starting with http:// or https://")
        return
    
    if not is_supported_url(url):
        await send_text_message(phone_number, "❌ Unsupported Platform\n\nSupported platforms:\n🎬 YouTube\n📱 Instagram\n🧵 Threads\n🎵 Spotify\n🎪 TikTok\n🐦 Twitter/X\n📘 Facebook\n📌 Pinterest")
        return
    
    platform = detect_platform(url)
    url_hash = get_url_hash(url)
    
    logger.info(f"📥 Processing {platform} URL from {phone_number}: {url}")
    
    # Check cache for duplicate
    if url_hash in download_cache:
        cached = download_cache[url_hash]
        user_sessions[phone_number] = {'url': url, 'info': cached}
        logger.info(f"💾 Using cached data for {platform} URL: {url}")
        await show_media_info_or_download(phone_number, cached, platform, from_cache=True)
        return
    
    # Show processing message with platform info
    await send_text_message(phone_number, f"🔄 Processing {platform.title()} link...")
    logger.info(f"🔄 Started processing {platform} content for {phone_number}")
    
    try:
        # Handle Spotify directly with enhanced processing
        if platform == 'spotify':
            await send_text_message(phone_number, "🎵 Processing Spotify track...")
            spotify_metadata = await process_spotify_url(url)
            if spotify_metadata:
                await send_text_message(phone_number, f"🎵 Downloading: {spotify_metadata['full_title']}")
                await download_and_send_spotify(phone_number, spotify_metadata)
            else:
                await send_text_message(phone_number, "❌ Could not process Spotify link\n\nMake sure the link is a valid Spotify track.")
            return
        
        # Handle Instagram - distinguish between video links and post links
        if platform == 'instagram':
            await send_text_message(phone_number, "📷 Processing Instagram content...")
            
            # Determine link type based on URL pattern
            url_lower = url.lower()
            is_video_link = '/reel/' in url_lower or '/reels/' in url_lower
            is_post_link = '/p/' in url_lower
            post_info = None  # Initialize for proper scoping
            
            logger.info(f"Instagram URL analysis - Video link: {is_video_link}, Post link: {is_post_link}, URL: {url}")
            
            # For post links, detect content type first to avoid unnecessary yt-dlp attempts
            if is_post_link:
                post_info = await detect_instagram_post_type(url)
                if post_info:
                    logger.info(f"Instagram post type detected: {post_info}")
                    # If it's a carousel, download all media
                    if post_info.get('is_carousel', False):
                        await send_text_message(phone_number, "🖼️ Downloading Instagram carousel post...")
                        instagram_data = await download_instagram_carousel(url, post_info)
                        if instagram_data:
                            await send_instagram_media_group(phone_number, instagram_data)
                            return
                        else:
                            await send_text_message(phone_number, "❌ Could not download Instagram carousel post\n\nThe content might be private or unsupported.")
                            return
            
            # For video links or when post type detection fails, proceed with normal download
            if is_video_link or (is_post_link and not post_info):
                await send_text_message(phone_number, "📹 Downloading Instagram video...")
        
        # Handle YouTube with enhanced error handling and logging
        if platform == 'youtube':
            await send_text_message(phone_number, "🎬 Processing YouTube video...")
            
            # Check if YouTube cookies are available
            if os.path.exists(YOUTUBE_COOKIES_FILE):
                file_size = os.path.getsize(YOUTUBE_COOKIES_FILE)
                if file_size > 0:
                    logger.info(f"🍪 Using YouTube cookies for authentication (file size: {file_size} bytes)")
                    await send_text_message(phone_number, "🔐 Using YouTube authentication cookies...")
                else:
                    logger.warning("⚠️ YouTube cookies file is empty")
                    await send_text_message(phone_number, "⚠️ YouTube cookies not available - download may be rate-limited...")
            else:
                logger.warning("⚠️ YouTube cookies file not found")
                await send_text_message(phone_number, "⚠️ YouTube cookies not found - download may be rate-limited...")
        
        # Extract media info with enhanced error handling
        logger.info(f"🔍 Extracting media info for {platform} URL: {url}")
        info = await get_media_info(url)
        
        if info:
            logger.info(f"✅ Media info extracted for {platform}: {info.get('title', 'Unknown')}")
            user_sessions[phone_number] = {'url': url, 'info': info}
            
            # Show media info and download options
            await show_media_info_or_download(phone_number, info, platform)
        else:
            logger.error(f"❌ Failed to extract media info for {platform} URL: {url}")
            
            # Provide specific error messages based on platform
            if platform == 'youtube':
                await send_text_message(phone_number, """⚠ Could not fetch media info from YouTube

Possible reasons:
• Video is private or age-restricted
• YouTube cookies are expired or invalid
• Video URL is incorrect
• Temporary YouTube rate limiting

Please check:
1. Your YouTube cookies file (ytcookies.txt)
2. Video URL is correct and accessible
3. Try again in a few minutes

If the problem persists, contact support.""")
            elif platform == 'instagram':
                await send_text_message(phone_number, """⚠ Could not fetch media info from Instagram

Possible reasons:
• Post is private or deleted
• Instagram cookies are expired or invalid
• URL is incorrect
• Temporary Instagram rate limiting

Please check:
1. Your Instagram cookies file (cookies.txt)
2. Post URL is correct and accessible
3. Try again in a few minutes

If the problem persists, contact support.""")
            else:
                await send_text_message(phone_number, f"❌ Could not process this {platform.title()} link\n\nThe content might be private or unsupported.")
    
    except Exception as e:
        logger.error(f"❌ Error processing {platform} link: {e}", exc_info=True)
        await send_text_message(phone_number, f"❌ Unexpected error processing {platform.title()} link\n\nPlease try again later.")

                            # Download thumbnail for better presentation
                            thumbnail_path = None
                            if info.get('thumbnail'):
                                try:
                                    thumbnail_path = os.path.join(TEMP_DIR, f"thumb_{hashlib.sha256(url.encode()).hexdigest()[:8]}.jpg")
                                    async with aiohttp.ClientSession() as session:
                                        async with session.get(info['thumbnail']) as response:
                                            if response.status == 200:
                                                with open(thumbnail_path, 'wb') as f:
                                                    f.write(await response.read())
                                except Exception as e:
                                    logger.debug(f"Instagram thumbnail download failed: {e}")
                                    thumbnail_path = None
                            
                            instagram_info = {
                                'title': info.get('title', 'Instagram Video')[:100],
                                'uploader': info.get('uploader', 'Instagram User'),
                                'platform': 'instagram',
                                'content_type': 'video',
                                'thumbnail': info.get('thumbnail'),
                                'local_thumbnail': thumbnail_path,
                                'url': url,
                                'yt_dlp_info': info
                            }
                            
                            # Cache the info and show video menu
                            download_cache[hashlib.sha256(url.encode()).hexdigest()] = instagram_info
                            user_sessions[phone_number] = {'url': url, 'info': instagram_info}
                            
                            await show_video_options(phone_number, instagram_info)
                            return
                        else:
                            # It's an image - auto download using fallback
                            await send_text_message(phone_number, "📥 Downloading Instagram image...")
                            # Use silent fallback for image posts to avoid error spam
                            file_path = await download_media(url, None, False, {'platform': 'instagram', 'silent': True})
                            if file_path:
                                await send_media_file(phone_number, file_path, info.get('title', 'Instagram Image'), 'image')
                            else:
                                raise Exception("yt-dlp download failed")
                            return
                            
                except Exception as e:
                    error_str = str(e).lower()
                    logger.debug(f"Instagram yt-dlp processing error: {e}")
                    
                    # Enhanced fallback handling - no scary error messages
                    try:
                        # Try instaloader fallback silently
                        instagram_data = await download_instagram_media(url)
                        if instagram_data:
                            await send_instagram_media_group(phone_number, instagram_data)
                        else:
                            # If instaloader also fails, try final approach
                            try:
                                # Try basic yt-dlp without authentication as last resort
                                file_path = await download_media(url, None, False, {'platform': 'instagram', 'no_auth': True})
                                if file_path:
                                    await send_media_file(phone_number, file_path, 'Instagram Content', 'mixed')
                                else:
                                    await send_text_message(phone_number, "❌ Could not download Instagram content\n\nThe content might be private or deleted.")
                            except Exception as final_error:
                                logger.debug(f"Instagram final fallback error: {final_error}")
                                await send_text_message(phone_number, "❌ Could not download Instagram content\n\nThe content might be private or deleted.")
                    except Exception as fallback_error:
                        logger.debug(f"Instagram instaloader fallback error: {fallback_error}")
                        # Try basic yt-dlp without authentication as last resort
                        try:
                            file_path = await download_media(url, None, False, {'platform': 'instagram', 'no_auth': True})
                            if file_path:
                                await send_media_file(phone_number, file_path, 'Instagram Content', 'mixed')
                            else:
                                await send_text_message(phone_number, "❌ Instagram download failed\n\nThe content might be private or deleted.")
                        except Exception as final_error:
                            logger.debug(f"Instagram final fallback error: {final_error}")
                            await send_text_message(phone_number, "❌ Instagram download failed\n\nThe content might be private or deleted.")
            return
        
        # Handle Threads - use similar logic to Instagram
        if platform == 'threads':
            await send_text_message(phone_number, "🧵 Processing Threads content...")
            
            # Determine link type - Threads posts can be videos or images
            url_lower = url.lower()
            
            try:
                # Extract metadata for Threads content
                base_opts = {
                    'quiet': True,
                    'no_warnings': True,
                    'extract_flat': False,
                    'skip_download': True,
                    'socket_timeout': 10,
                    'retries': 1,
                    'http_headers': {
                        'User-Agent': USER_AGENTS.get('instagram', USER_AGENTS['default'])
                    }
                }
                
                # Use Instagram authentication for Threads since they share the same backend
                ydl_opts = instagram_auth.get_ytdl_opts(base_opts)
                logger.debug("🔄 Using Instagram authentication for Threads content extraction")
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    
                    # Check if it's a video
                    formats = info.get('formats', [])
                    has_video = any(f.get('vcodec', 'none') != 'none' for f in formats)
                    
                    if has_video:
                        # For Threads videos, show video/audio selection menu like other social platforms
                        # Download thumbnail for better presentation
                        thumbnail_path = None
                        if info.get('thumbnail'):
                            try:
                                thumbnail_path = os.path.join(TEMP_DIR, f"thumb_{hashlib.sha256(url.encode()).hexdigest()[:8]}.jpg")
                                async with aiohttp.ClientSession() as session:
                                    async with session.get(info['thumbnail']) as response:
                                        if response.status == 200:
                                            with open(thumbnail_path, 'wb') as f:
                                                f.write(await response.read())
                            except Exception as e:
                                logger.debug(f"Threads thumbnail download failed: {e}")
                                thumbnail_path = None
                        
                        threads_info = {
                            'title': info.get('title', 'Threads Video')[:100],
                            'uploader': info.get('uploader', 'Threads User'),
                            'platform': 'threads',
                            'content_type': 'video',
                            'thumbnail': info.get('thumbnail'),
                            'local_thumbnail': thumbnail_path,
                            'url': url,
                            'yt_dlp_info': info
                        }
                        
                        # Cache the info and show video menu
                        download_cache[hashlib.sha256(url.encode()).hexdigest()] = threads_info
                        user_sessions[phone_number] = {'url': url, 'info': threads_info}
                        
                        await show_video_options(phone_number, threads_info)
                        return
                    else:
                        # It's an image - auto download using Instagram fallback logic
                        await send_text_message(phone_number, "⚡ Downloading Threads image...")
                        file_path = await download_media(url, None, False, {'platform': 'threads'})
                        if file_path:
                            await send_media_file(phone_number, file_path, info.get('title', 'Threads Image'), 'image')
                        else:
                            raise Exception("yt-dlp download failed")
                        return
                        
            except Exception as e:
                logger.debug(f"Threads yt-dlp processing error: {e}")
                # Enhanced fallback handling with multiple methods
                
                # Method 1: Try Instagram download method since Threads uses same backend
                try:
                    await send_text_message(phone_number, "🔄 Trying Instagram fallback method...")
                    logger.info("🧵 Attempting Threads fallback using Instagram downloader")
                    instagram_data = await download_instagram_media(url)
                    if instagram_data:
                        logger.info("🧵 Successfully downloaded Threads content using Instagram method")
                        await send_instagram_media_group(phone_number, instagram_data)
                        return
                    logger.debug("🧵 Instagram fallback method failed for Threads")
                except Exception as instagram_fallback_error:
                    logger.debug(f"Threads Instagram fallback error: {instagram_fallback_error}")
                
                # Method 2: Try basic yt-dlp without authentication
                try:
                    await send_text_message(phone_number, "🔄 Trying basic extraction...")
                    logger.info("🧵 Attempting Threads fallback using basic yt-dlp")
                    file_path = await download_media(url, None, False, {'platform': 'threads', 'no_auth': True})
                    if file_path:
                        logger.info("🧵 Successfully downloaded Threads content using basic method")
                        await send_media_file(phone_number, file_path, 'Threads Content', 'mixed')
                        return
                    logger.debug("🧵 Basic yt-dlp method failed for Threads")
                except Exception as basic_fallback_error:
                    logger.debug(f"Threads basic fallback error: {basic_fallback_error}")
                
                # Method 3: Try direct media extraction (new fallback)
                try:
                    await send_text_message(phone_number, "🔄 Trying direct extraction...")
                    logger.info("🧵 Attempting Threads fallback using direct extraction")
                    media_info = await extract_direct_media_url(url, 'threads')
                    if media_info:
                        file_path = await download_direct_media(media_info['url'], 'threads')
                        if file_path:
                            logger.info("🧵 Successfully downloaded Threads content using direct method")
                            await send_media_file(phone_number, file_path, media_info.get('title', 'Threads Content'), media_info.get('type', 'mixed'))
                            return
                    logger.debug("🧵 Direct extraction method failed for Threads")
                except Exception as direct_fallback_error:
                    logger.debug(f"Threads direct fallback error: {direct_fallback_error}")
                
                # Final fallback message
                logger.warning(f"🧵 All Threads fallback methods failed for URL: {url}")
                await send_text_message(phone_number, "❌ Could not download Threads content\n\nThe content might be private, deleted, or not supported. Threads content sometimes requires being logged in to the platform.")
            return
        
        # Enhanced media info extraction with multiple attempts
        info = await get_media_info_with_retries(url, platform)
        
        if not info:
            await send_text_message(phone_number, f"⚠️ Could not fetch media info from {platform.title()}\n\nTrying direct download method...")
            
            # Try direct extraction as fallback
            media_info = await extract_direct_media_url(url, platform)
            if media_info:
                await send_text_message(phone_number, "⚡ Downloading content directly...")
                file_path = await download_direct_media(media_info['url'], platform)
                if file_path:
                    await send_media_file(phone_number, file_path, media_info['title'], media_info['type'])
                else:
                    await send_text_message(phone_number, f"❌ Download failed\n\nCould not download content from {platform.title()}.")
            else:
                await send_text_message(phone_number, f"❌ Could not process this {platform.title()} link\n\nThe content might be private or unsupported.")
            return
        
        # Cache the info
        download_cache[url_hash] = info
        user_sessions[phone_number] = {'url': url, 'info': info}
        
        await show_media_info_or_download(phone_number, info, platform)
    
    except Exception as e:
        logger.error(f"Link processing error: {e}")
        error_msg = f"❌ Processing failed\n\nError processing {platform.title()} link. Please try again or use a different link."
        await send_text_message(phone_number, error_msg)

async def get_media_info_with_retries(url: str, platform: str, max_retries: int = 2) -> Optional[Dict]:
    """Get media info with retries and platform-specific optimizations"""
    for attempt in range(max_retries):
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True,
                'socket_timeout': 20 + (attempt * 10),  # Increase timeout on retries
                'retries': 1,
                'noplaylist': True
            }
            # Use YouTube cookies if available
            try:
                if platform == 'youtube' and os.path.exists(YOUTUBE_COOKIES_FILE):
                    ydl_opts['cookiefile'] = YOUTUBE_COOKIES_FILE
            except Exception:
                pass
            
            # Platform-specific optimizations
            if platform == 'pinterest':
                ydl_opts.update({
                    'http_headers': {
                        'User-Agent': USER_AGENTS['pinterest'],
                        'Referer': 'https://www.pinterest.com/',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
                    }
                })
            elif platform == 'instagram':
                ydl_opts.update({
                    'http_headers': {
                        'User-Agent': USER_AGENTS['instagram']
                    }
                })
            elif platform == 'threads':
                # Threads uses the same authentication as Instagram
                ydl_opts.update({
                    'http_headers': {
                        'User-Agent': USER_AGENTS.get('instagram', USER_AGENTS['default'])
                    }
                })
            elif platform == 'facebook':
                ydl_opts.update({
                    'http_headers': {
                        'User-Agent': USER_AGENTS['facebook']
                    }
                })
            elif platform == 'tiktok':
                ydl_opts.update({
                    'http_headers': {
                        'User-Agent': USER_AGENTS['tiktok'],
                        'Referer': 'https://www.tiktok.com/'
                    }
                })
            
            # Apply Instagram authentication for Instagram and Threads
            if platform in ['instagram', 'threads']:
                ydl_opts = instagram_auth.get_ytdl_opts(ydl_opts)
                logger.debug(f"🔑 Using Instagram authentication for {platform} media info")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Download thumbnail if available
                thumbnail_path = None
                if info.get('thumbnail'):
                    try:
                        response = requests.get(info['thumbnail'], timeout=10)
                        if response.status_code == 200:
                            thumbnail_path = f"{TEMP_DIR}/{info.get('id', 'temp')}_{int(time.time())}.jpg"
                            with open(thumbnail_path, 'wb') as f:
                                f.write(response.content)
                    except Exception as e:
                        logger.warning(f"Thumbnail download failed: {e}")
                
                content_type = detect_content_type(url, info)
                
                return {
                    'title': info.get('title', 'Unknown Title'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail'),
                    'local_thumbnail': thumbnail_path,
                    'uploader': info.get('uploader', 'Unknown'),
                    'id': info.get('id', ''),
                    'platform': platform,
                    'content_type': content_type,
                    'timestamp': time.time(),
                    'source': 'yt-dlp'
                }
                
        except Exception as ytdlp_error:
            logger.warning(f"yt-dlp attempt {attempt + 1} failed: {ytdlp_error}")
            if attempt == max_retries - 1:  # Last attempt
                # For Instagram, try instaloader first
                if platform == 'instagram':
                    try:
                        instagram_data = await download_instagram_media(url)
                        if instagram_data:
                            return {
                                'title': instagram_data.get('title', 'Instagram Post'),
                                'duration': 0,
                                'thumbnail': None,
                                'local_thumbnail': None,
                                'uploader': instagram_data.get('owner', 'Instagram'),
                                'id': get_url_hash(url)[:8],
                                'platform': platform,
                                'content_type': 'video' if instagram_data.get('is_video') else 'image',
                                'timestamp': time.time(),
                                'source': 'instaloader',
                                'instagram_data': instagram_data
                            }
                    except Exception as e:
                        logger.debug(f"Instagram instaloader retry failed: {e}")
                
                # Try direct extraction fallback
                media_info = await extract_direct_media_url(url, platform)
                if media_info:
                    return {
                        'title': media_info.get('title', f'{platform.title()} Media'),
                        'duration': 0,
                        'thumbnail': None,
                        'local_thumbnail': None,
                        'uploader': platform.title(),
                        'id': get_url_hash(url)[:8],
                        'platform': platform,
                        'content_type': media_info['type'],
                        'timestamp': time.time(),
                        'source': 'direct',
                        'direct_url': media_info['url']
                    }
    
    return None

async def show_media_info_or_download(phone_number: str, info: Dict, platform: str, from_cache: bool = False):
    """Show media info or auto-download based on content type"""
    content_type = info.get('content_type', 'mixed')
    
    # Special handling for Instagram instaloader data
    if info.get('source') == 'instaloader' and info.get('instagram_data'):
        await send_text_message(phone_number, "📥 Processing Instagram content...")
        await send_instagram_media_group(phone_number, info['instagram_data'])
        return
    
    # Auto-download for images and mixed content that turns out to be images
    if content_type == 'image':
        await auto_download_content(phone_number, info)
    elif content_type == 'mixed':
        # For mixed content, try to determine the actual type and auto-download if it's an image
        await smart_content_handler(phone_number, info, platform)
    elif platform == 'youtube':
        # Show quality menu for YouTube
        await show_media_info(phone_number, info, platform, from_cache)
    else:
        # Show video/audio options for other video platforms
        await show_video_options(phone_number, info)

async def smart_content_handler(phone_number: str, info: Dict, platform: str):
    """Smart handler for mixed content - determines if it's image or video and acts accordingly"""
    await send_text_message(phone_number, "⚡ Analyzing content...")
    
    try:
        # If we have direct_url from custom extraction, check the content type
        if info.get('source') == 'direct' and info.get('direct_url'):
            # Try to determine content type from URL or headers
            content_type_result = await determine_media_type(info['direct_url'])
            if content_type_result == 'image':
                await send_text_message(phone_number, "📥 Downloading image...")
                await auto_download_with_msg(phone_number, info)
                return
            elif content_type_result == 'video':
                await show_video_options(phone_number, info)
                return
        
        # For other mixed content, try yt-dlp first to get format info
        url = user_sessions[phone_number]['url']
        
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
                'skip_download': True,
                'socket_timeout': 10,
                'retries': 1
            }
            # Use YouTube cookies for mixed-content analysis if available
            try:
                if platform == 'youtube' and os.path.exists(YOUTUBE_COOKIES_FILE):
                    ydl_opts['cookiefile'] = YOUTUBE_COOKIES_FILE
            except Exception:
                pass
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                detailed_info = ydl.extract_info(url, download=False)
                
                formats = detailed_info.get('formats', [])
                has_video = any(f.get('vcodec', 'none') != 'none' for f in formats)
                
                if not has_video:
                    # It's likely an image - auto download
                    await send_text_message(phone_number, "📥 Downloading image...")
                    await auto_download_with_msg(phone_number, info)
                else:
                    # It's a video - show options
                    await show_video_options(phone_number, info)
                    
        except Exception:
            # If yt-dlp fails, try direct extraction
            media_info = await extract_direct_media_url(url, platform)
            if media_info:
                if media_info['type'] == 'image':
                    await send_text_message(phone_number, "📥 Downloading image...")
                    file_path = await download_direct_media(media_info['url'], platform)
                    if file_path:
                        await send_media_file(phone_number, file_path, media_info['title'], 'image')
                    else:
                        await send_text_message(phone_number, "❌ Download failed")
                else:
                    await show_video_options(phone_number, info)
            else:
                await send_text_message(phone_number, "❌ Could not determine content type")
                
    except Exception as e:
        logger.error(f"Smart content handler error: {e}")
        await send_text_message(phone_number, "❌ Processing failed")

async def determine_media_type(url: str) -> str:
    """Determine media type from URL headers"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                content_type = response.headers.get('content-type', '').lower()
                if 'image' in content_type:
                    return 'image'
                elif 'video' in content_type:
                    return 'video'
                else:
                    # Check URL extension as fallback
                    if any(ext in url.lower() for ext in IMAGE_EXTENSIONS):
                        return 'image'
                    else:
                        return 'video'
    except Exception:
        # Fallback to URL-based detection
        if any(ext in url.lower() for ext in IMAGE_EXTENSIONS):
            return 'image'
        return 'video'

async def auto_download_with_msg(phone_number: str, info: Dict):
    """Auto download with existing processing message"""
    try:
        url = user_sessions[phone_number]['url']
        file_path = await download_media(url, info=info)
        
        if file_path and os.path.exists(file_path):
            await send_media_file(phone_number, file_path, info['title'], info.get('content_type', 'image'))
        else:
            await send_text_message(phone_number, "❌ Download failed")
    
    except Exception as e:
        logger.error(f"Auto download error: {e}")
        await send_text_message(phone_number, "❌ Download failed")

async def auto_download_content(phone_number: str, info: Dict):
    """Auto download images and simple posts"""
    await send_text_message(phone_number, "⚡ Downloading content...")
    
    try:
        url = user_sessions[phone_number]['url']
        file_path = await download_media(url, info=info)
        
        if file_path and os.path.exists(file_path):
            await send_media_file(phone_number, file_path, info['title'], info['content_type'])
        else:
            await send_text_message(phone_number, "❌ Download failed")
    
    except Exception as e:
        logger.error(f"Auto download error: {e}")
        await send_text_message(phone_number, "❌ Download failed")

async def send_media_file(phone_number: str, file_path: str, title: str, content_type: str):
    """Send media file to user"""
    try:
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            await send_text_message(phone_number, "❌ File too large (max 50MB)")
            cleanup_file(file_path)
            return
        
        await send_text_message(phone_number, "🚀 Sending...")
        
        size_mb = file_size / (1024 * 1024)
        
        try:
            # Create caption
            safe_title = title
            if content_type == 'image':
                caption = f"📷 {safe_title}\n\n✅ Image • {size_mb:.1f}MB"
                await send_image_message(phone_number, file_path, caption)
            else:
                # Determine if it's video or other
                caption = f"🎬 {safe_title}\n\n✅ Video • {size_mb:.1f}MB"
                await send_video_message(phone_number, file_path, caption)
            
        except Exception as e:
            logger.error(f"Send file error: {e}")
            await send_text_message(phone_number, "❌ Failed to send file")
        
        finally:
            cleanup_file(file_path)
            
    except Exception as e:
        logger.error(f"File send process error: {e}")
        cleanup_file(file_path)

async def show_media_info(phone_number: str, info: Dict, platform: str, from_cache: bool = False):
    """Show media info with download options"""
    title = info['title'][:60] + "..." if len(info['title']) > 60 else info['title']
    safe_title = title
    safe_uploader = info.get('uploader', 'Unknown')
    safe_platform = platform.title()
    
    duration = info.get('duration', 0)
    duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Unknown"
    
    caption = f"🎬 {safe_title}\n\n⏱ Duration: {duration_str}\n👤 Uploader: {safe_uploader}\n🎬 Platform: {safe_platform}\n\nChoose download quality:"
    
    # Send interactive message with quality options
    button_texts = ["1080p", "720p", "480p", "360p", "MP3 Audio"]
    await send_interactive_message(phone_number, "Download Quality", caption, button_texts)

async def show_video_options(phone_number: str, info: Dict):
    """Show video/audio options for social platforms"""
    title = info['title'][:60] + "..." if len(info['title']) > 60 else info['title']
    safe_title = title
    safe_uploader = info.get('uploader', 'Unknown')
    safe_platform = info['platform'].title()
    
    caption = f"🎬 {safe_title}\n\n👤 Uploader: {safe_uploader}\n🎬 Platform: {safe_platform}\n\nChoose download type:"
    
    # Send interactive message with options
    button_texts = ["🎬 Video", "🎧 Audio"]
    await send_interactive_message(phone_number, "Download Type", caption, button_texts)

async def handle_qr_text(phone_number: str, user_text: str):
    """Handle QR code text input"""
    try:
        if not user_text:
            await send_text_message(phone_number, "❌ Empty text\n\nPlease send some text or a link to generate QR code.")
            return
        
        # Send processing message
        await send_text_message(phone_number, "🔄 Generating QR code...")
        
        # Generate QR code
        qr_file_path = await generate_qr_with_text(user_text)
        
        # Send QR code image
        caption = f"📲 QR Code Generated\n\n📝 Content: {user_text[:50]}{'...' if len(user_text) > 50 else ''}\n\n✨ Powered by @abdifahadi"
        await send_image_message(phone_number, qr_file_path, caption)
        
        # Clean up file
        cleanup_file(qr_file_path)
        
    except Exception as e:
        logger.error(f"❌ QR generation error for {phone_number}: {e}")
        logger.error(f"❌ QR generation failed for text: {user_text[:100]}...")
        
        await send_text_message(phone_number, "⚠️ QR code generation failed. Please try again.")

async def download_and_send_media(phone_number: str, quality: str, audio_only: bool):
    """Download and send media file"""
    if phone_number not in user_sessions:
        await send_text_message(phone_number, "Session expired. Please send the link again.")
        return
    
    url = user_sessions[phone_number]['url']
    info = user_sessions[phone_number]['info']
    platform = detect_platform(url)
    
    # Show download progress
    progress_text = "🎵 Downloading audio..." if audio_only else f"⚡ Downloading {quality}..."
    await send_text_message(phone_number, progress_text)
    
    try:
        file_path = await download_media(url, quality, audio_only, info)
        
        if not file_path or not os.path.exists(file_path):
            await send_text_message(phone_number, "❌ Download failed")
            return
        
        file_size = os.path.getsize(file_path)
        if file_size > MAX_FILE_SIZE:
            await send_text_message(phone_number, "❌ File too large (max 50MB)\n\nTry a lower quality.")
            cleanup_file(file_path)
            return
        
        await send_text_message(phone_number, "📤 Sending...")
        
        # Send the file
        title = info['title']
        size_mb = file_size / (1024 * 1024)
        
        try:
            if audio_only:
                caption = f"🎵 {title}\n\n✅ 320kbps MP3 • {size_mb:.1f}MB"
                await send_audio_message(phone_number, file_path)
                await send_text_message(phone_number, caption)
            else:
                caption = f"🎬 {title}\n\n✅ {quality} MP4 • {size_mb:.1f}MB"
                await send_video_message(phone_number, file_path, caption)
            
        except Exception as e:
            logger.error(f"Send file error: {e}")
            await send_text_message(phone_number, "❌ Failed to send file")
        
        finally:
            cleanup_file(file_path)
    
    except Exception as e:
        logger.error(f"Download error: {e}")
        error_str = str(e).lower()
        
        # Provide specific error messages based on platform and error type
        if platform == 'youtube':
            if any(term in error_str for term in ['drm', 'protected', 'copyright']):
                await send_text_message(phone_number, """❌ DRM Protected Content

This YouTube video is copyright protected and cannot be downloaded.

Possible reasons:
• Video is DRM-protected
• Content owner has disabled downloads
• Video is from a premium service

Please try a different video or platform.""")
            elif any(term in error_str for term in ['private', 'unavailable', 'access denied', 'forbidden']):
                await send_text_message(phone_number, """❌ Access Denied

This YouTube video is private or unavailable.

Possible reasons:
• Video is private or deleted
• YouTube cookies are expired or invalid
• Video URL is incorrect
• Account restrictions

Please check:
1. Video URL is correct and accessible
2. Your YouTube cookies file (ytcookies.txt)
3. Try again in a few minutes""")
            elif any(term in error_str for term in ['age', 'restricted']):
                await send_text_message(phone_number, """❌ Age Restricted

This YouTube video is age-restricted and cannot be downloaded.

Please try a different video that is not age-restricted.""")
            elif any(term in error_str for term in ['login', 'authentication', 'unauthorized']):
                await send_text_message(phone_number, """⚠️ Authentication Required

YouTube requires authentication to download this video.

Please check:
1. Your YouTube cookies file (ytcookies.txt) is valid and not expired
2. You're logged into YouTube in your browser when extracting cookies
3. Try refreshing your cookies file with fresh session cookies

To refresh cookies:
1. Log into YouTube in your browser
2. Use a cookie extraction tool to export cookies to ytcookies.txt
3. Restart the bot""")
            elif "429" in error_str or "too many requests" in error_str:
                await send_text_message(phone_number, """⚠️ Rate Limit Exceeded

YouTube is rate-limiting requests. This is temporary.

Please try again in a few minutes or check your YouTube cookies for better rate limiting handling.""")
            else:
                await send_text_message(phone_number, f"""❌ YouTube Download Failed

An error occurred while downloading the YouTube video.

Error details: {str(e)[:100]}...

Possible solutions:
1. Check your YouTube cookies file (ytcookies.txt)
2. Try a different quality option
3. Try again in a few minutes
4. Verify the video URL is correct

If the problem persists, contact support.""")
        elif error_str == "DRM_PROTECTED":
            await send_text_message(phone_number, "❌ DRM Protected Content\n\nThis content is copyright protected.")
        elif error_str == "ACCESS_DENIED":
            await send_text_message(phone_number, "❌ Access Denied\n\nThis content is private or unavailable.")
        elif error_str == "AGE_RESTRICTED":
            await send_text_message(phone_number, "❌ Age Restricted\n\nThis content is age-restricted.")
        else:
            await send_text_message(phone_number, "❌ Download failed")

async def download_and_send_spotify(phone_number: str, spotify_metadata: Dict):
    """Handle Spotify download and send with proper filename"""
    try:
        file_path = await download_media_with_filename(
            spotify_metadata['search_query'], 
            filename=spotify_metadata['filename'],
            audio_only=True
        )
        
        if file_path and os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            if file_size > MAX_FILE_SIZE:
                await send_text_message(phone_number, "❌ File too large (max 50MB)")
                cleanup_file(file_path)
                return
            
            await send_text_message(phone_number, "📤 Sending...")
            
            try:
                size_mb = file_size / (1024 * 1024)
                caption = f"🎵 {spotify_metadata['full_title']}\n\n✅ 320kbps MP3 • {size_mb:.1f}MB"
                await send_audio_message(phone_number, file_path)
                await send_text_message(phone_number, caption)
            except Exception:
                await send_text_message(phone_number, "❌ Failed to send file")
            finally:
                cleanup_file(file_path)
        else:
            await send_text_message(phone_number, "❌ Download failed")
    except Exception as e:
        logger.error(f"Spotify download error: {e}")
        await send_text_message(phone_number, "❌ Download failed")

# FastAPI app for WhatsApp webhook
app = FastAPI()

@app.get("/webhook")
async def verify_webhook(request: Request):
    """Verify webhook for WhatsApp API"""
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")
    
    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("✅ Webhook verified successfully")
            return int(challenge)
        else:
            logger.error("❌ Webhook verification failed")
            raise HTTPException(status_code=403, detail="Verification failed")
    else:
        logger.error("❌ Missing parameters for webhook verification")
        raise HTTPException(status_code=400, detail="Missing parameters")

@app.post("/webhook")
async def handle_webhook(request: Request, background_tasks: BackgroundTasks):
    """Handle incoming WhatsApp messages"""
    body = await request.json()
    logger.info(f"📥 Received webhook: {json.dumps(body, indent=2)}")
    
    try:
        # Process the message in the background
        background_tasks.add_task(process_whatsapp_message, body)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"❌ Error handling webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

async def process_whatsapp_message(body: Dict):
    """Process incoming WhatsApp message"""
    try:
        # Extract message details
        entry = body.get("entry", [])
        if not entry:
            return
        
        for entry_item in entry:
            changes = entry_item.get("changes", [])
            for change in changes:
                value = change.get("value", {})
                messages = value.get("messages", [])
                
                for message in messages:
                    phone_number = message.get("from")
                    message_type = message.get("type")
                    
                    logger.info(f"📞 Processing {message_type} message from {phone_number}")
                    
                    # Handle different message types
                    if message_type == "text":
                        text_body = message.get("text", {}).get("body", "")
                        await handle_text_message(phone_number, text_body)
                    elif message_type == "interactive":
                        interactive_body = message.get("interactive", {})
                        if interactive_body.get("type") == "button_reply":
                            button_reply = interactive_body.get("button_reply", {})
                            button_id = button_reply.get("id")
                            button_title = button_reply.get("title")
                            await handle_button_reply(phone_number, button_id, button_title)
                        elif interactive_body.get("type") == "list_reply":
                            list_reply = interactive_body.get("list_reply", {})
                            list_id = list_reply.get("id")
                            list_title = list_reply.get("title")
                            await handle_list_reply(phone_number, list_id, list_title)
                    elif message_type == "image":
                        await send_text_message(phone_number, "📷 Image received. I can only process links for downloading.")
                    elif message_type == "video":
                        await send_text_message(phone_number, "🎥 Video received. I can only process links for downloading.")
                    elif message_type == "audio":
                        await send_text_message(phone_number, "🎵 Audio received. I can only process links for downloading.")
                    elif message_type == "document":
                        await send_text_message(phone_number, "📄 Document received. I can only process links for downloading.")
                    elif message_type == "location":
                        await send_text_message(phone_number, "📍 Location received. I can only process links for downloading.")
                    elif message_type == "contacts":
                        await send_text_message(phone_number, "👤 Contact received. I can only process links for downloading.")
                    else:
                        await send_text_message(phone_number, "❓ Unknown message type. Please send a text message with a link to download.")
    except Exception as e:
        logger.error(f"❌ Error processing WhatsApp message: {e}")

async def handle_text_message(phone_number: str, text: str):
    """Handle incoming text message"""
    text = text.strip()
    
    # Handle commands
    if text.lower() in ["/start", "start", "hi", "hello", "hey"]:
        await handle_welcome_message(phone_number)
    elif text.lower() in ["/help", "help"]:
        await handle_help_message(phone_number)
    elif text.lower() in ["/qr", "qr", "qrcode"]:
        await handle_qr_message(phone_number)
    elif text.startswith(("http://", "https://")):
        # Handle URL
        await handle_link_message(phone_number, text)
    else:
        # Handle QR code generation for any other text
        await handle_qr_text(phone_number, text)

async def handle_button_reply(phone_number: str, button_id: str, button_title: str):
    """Handle button reply from interactive message"""
    if phone_number not in user_sessions:
        await send_text_message(phone_number, "Session expired. Please send the link again.")
        return
    
    # Check if this is a YouTube quality selection
    if button_id.startswith("button_"):
        if button_title == "1080p":
            await download_and_send_media(phone_number, "1080p", False)
        elif button_title == "720p":
            await download_and_send_media(phone_number, "720p", False)
        elif button_title == "480p":
            await download_and_send_media(phone_number, "480p", False)
        elif button_title == "360p":
            await download_and_send_media(phone_number, "360p", False)
        elif button_title == "MP3 Audio":
            await download_and_send_media(phone_number, None, True)
        elif button_title == "🎬 Video":
            await download_and_send_media(phone_number, "best", False)
        elif button_title == "🎧 Audio":
            await download_and_send_media(phone_number, None, True)
        else:
            await send_text_message(phone_number, "❓ Unknown option selected.")

async def handle_list_reply(phone_number: str, list_id: str, list_title: str):
    """Handle list reply from interactive message"""
    # Currently not implemented, but can be used for more complex menus
    await send_text_message(phone_number, f"Selected: {list_title}")

def cleanup_old_files():
    """Clean up old files periodically"""
    try:
        directories = [TEMP_DIR, DOWNLOADS_DIR]
        current_time = time.time()
        
        for directory in directories:
            if os.path.exists(directory):
                for filename in os.listdir(directory):
                    file_path = os.path.join(directory, filename)
                    if os.path.isfile(file_path):
                        # Remove files older than 30 minutes
                        if current_time - os.path.getctime(file_path) > 1800:
                            os.remove(file_path)
    except Exception as e:
        logger.warning(f"Cleanup error: {e}")

async def periodic_cleanup():
    """Periodic cleanup task"""
    while True:
        await asyncio.sleep(1800)  # 30 minutes
        cleanup_old_files()
        
        # Clear old cache entries
        current_time = time.time()
        expired_keys = [k for k, v in download_cache.items() 
                       if current_time - v.get('timestamp', 0) > 7200]  # 2 hours
        for key in expired_keys:
            del download_cache[key]

async def main():
    """Main function"""
    logger.info("🚀 Starting Ultra-Fast Media Downloader WhatsApp Bot...")
    
    # Ensure directories exist
    ensure_directories()
    
    # Validate Instagram setup
    await validate_instagram_setup()
    
    # Validate YouTube setup
    await validate_youtube_setup()
    
    # Check FFmpeg
    if not shutil.which('ffmpeg'):
        logger.warning("⚠️ FFmpeg not found - some features may not work")
    
    # Start periodic cleanup
    asyncio.create_task(periodic_cleanup())
    
    logger.info("✅ WhatsApp Bot is ready!")
    logger.info("📱 Supported: YouTube, Instagram, TikTok, Spotify, Twitter, Facebook, Pinterest")
    logger.info("🎯 Enhanced: Image detection, Pinterest videos, fallback downloads")
    
    # Start FastAPI server
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))

if __name__ == "__main__":
    asyncio.run(main())