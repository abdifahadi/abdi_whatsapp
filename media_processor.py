import os
import asyncio
import aiohttp
import tempfile
import hashlib
import time
import json
import re
import uuid
import logging
import requests
from pathlib import Path
from typing import Dict, Optional, List, Any
from bs4 import BeautifulSoup
import instaloader
import yt_dlp
import qrcode
from PIL import Image, ImageDraw, ImageFont

from config import (
    MAX_FILE_SIZE, DOWNLOADS_DIR, TEMP_DIR,
    INSTAGRAM_COOKIES_FILE, INSTAGRAM_REQUEST_DELAY,
    PROXY_HOST, PROXY_PORT, PROXY_USER, PROXY_PASS,
    YOUTUBE_COOKIES_FILE
)

logger = logging.getLogger(__name__)

class MediaProcessor:
    """Handles media processing, downloading, and QR code generation"""
    
    def __init__(self):
        self.download_cache = {}
        self.instagram_auth = InstagramCookieManager()
        
        # Platform patterns
        self.platform_patterns = {
            'youtube': r'(?:youtube\.com|youtu\.be|music\.youtube\.com)',
            'pinterest': r'(?:pinterest\.com|pin\.it)',
            'instagram': r'(?:instagram\.com|instagr\.am)',
            'threads': r'(?:threads\.net)',
            'tiktok': r'(?:tiktok\.com|vm\.tiktok\.com)',
            'facebook': r'(?:facebook\.com|fb\.watch|fb\.me)',
            'spotify': r'(?:spotify\.com|open\.spotify\.com)',
            'twitter': r'(?:twitter\.com|x\.com|t\.co)'
        }
        
        # Video qualities
        self.video_qualities = {
            "1080p": "best[height<=1080][height>720][ext=mp4]/best[height<=1080][height>720]/bestvideo[height<=1080][height>720]+bestaudio/best[height<=1080]",
            "720p": "best[height<=720][height>480][ext=mp4]/best[height<=720][height>480]/bestvideo[height<=720][height>480]+bestaudio/best[height<=720]",
            "480p": "best[height<=480][height>360][ext=mp4]/best[height<=480][height>360]/bestvideo[height<=480][height>360]+bestaudio/best[height<=480]",
            "360p": "best[height<=360][height>240][ext=mp4]/best[height<=360][height>240]/bestvideo[height<=360][height>240]+bestaudio/best[height<=360]",
            "240p": "best[height<=240][height>144][ext=mp4]/best[height<=240][height>144]/bestvideo[height<=240][height>144]+bestaudio/best[height<=240]",
            "144p": "worst[height<=144][ext=mp4]/worst[height<=144]/bestvideo[height<=144]+bestaudio/worst"
        }
        
        # User agents
        self.user_agents = {
            'default': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'pinterest': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'instagram': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1',
            'facebook': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0',
            'tiktok': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    
    def detect_platform(self, url: str) -> Optional[str]:
        """Detect platform from URL"""
        url_lower = url.lower()
        
        if url_lower.startswith('ytsearch'):
            return 'youtube'

        for platform, pattern in self.platform_patterns.items():
            if re.search(pattern, url_lower):
                return platform
        
        return None
    
    def is_supported_url(self, url: str) -> bool:
        """Check if URL is from supported platform"""
        return self.detect_platform(url) is not None
    
    def get_url_hash(self, url: str) -> str:
        """Generate hash for URL"""
        return hashlib.md5(url.encode()).hexdigest()
    
    def sanitize_filename(self, title: str, max_length: int = 100) -> str:
        """Sanitize title for filename"""
        if not title or not title.strip():
            return f"media_{int(time.time())}"
        
        try:
            import unicodedata
            safe_title = unicodedata.normalize('NFKD', title)
            safe_title = safe_title.encode('ascii', 'ignore').decode('ascii')
        except:
            safe_title = title
        
        safe_title = re.sub(r'[<>:"/\\|?*]', '', safe_title)
        safe_title = re.sub(r'\.{2,}', '.', safe_title)
        safe_title = re.sub(r'\s+', ' ', safe_title).strip()
        safe_title = safe_title.strip('. ')
        
        safe_title = re.sub(r'[^\w\s\-_.]', '', safe_title)
        
        if len(safe_title) > max_length:
            safe_title = safe_title[:max_length].rsplit(' ', 1)[0]
        
        safe_title = safe_title.rstrip('.,!?;:-_ ')
        
        if not safe_title or len(safe_title) < 3:
            safe_title = f"media_{int(time.time())}"
        
        return safe_title
    
    async def process_url(self, url: str, platform: str) -> Dict:
        """Process URL and return result"""
        try:
            # Check cache
            url_hash = self.get_url_hash(url)
            if url_hash in self.download_cache:
                cached = self.download_cache[url_hash]
                logger.info(f"💾 Using cached data for {platform}")
                return {'success': True, 'type': 'menu', 'info': cached}
            
            # Handle Spotify
            if platform == 'spotify':
                return await self.process_spotify(url)
            
            # Handle Instagram
            elif platform == 'instagram':
                return await self.process_instagram(url)
            
            # Handle Threads
            elif platform == 'threads':
                return await self.process_threads(url)
            
            # Handle YouTube
            elif platform == 'youtube':
                return await self.process_youtube(url)
            
            # Handle other platforms
            else:
                return await self.process_generic(url, platform)
                
        except Exception as e:
            logger.error(f"❌ URL processing error: {e}")
            return {'success': False, 'error': 'Processing failed'}
    
    async def process_spotify(self, url: str) -> Dict:
        """Process Spotify URL"""
        try:
            spotify_metadata = await self.extract_spotify_metadata(url)
            if spotify_metadata:
                file_path = await self.download_media_with_filename(
                    spotify_metadata['search_query'], 
                    filename=spotify_metadata['filename'],
                    audio_only=True
                )
                
                if file_path:
                    return {
                        'success': True,
                        'type': 'direct_download',
                        'file_path': file_path,
                        'title': spotify_metadata['full_title'],
                        'media_type': 'MP3 Audio'
                    }
                else:
                    return {'success': False, 'error': 'Download failed'}
            else:
                return {'success': False, 'error': 'Could not process Spotify link'}
                
        except Exception as e:
            logger.error(f"Spotify processing error: {e}")
            return {'success': False, 'error': 'Spotify processing failed'}
    
    async def process_instagram(self, url: str) -> Dict:
        """Process Instagram URL"""
        try:
            # Try direct download first
            file_path = await self.download_media(url, platform='instagram')
            
            if file_path:
                return {
                    'success': True,
                    'type': 'direct_download',
                    'file_path': file_path,
                    'title': 'Instagram Content',
                    'media_type': 'Video/Image'
                }
            else:
                return {'success': False, 'error': 'Instagram download failed'}
                
        except Exception as e:
            logger.error(f"Instagram processing error: {e}")
            return {'success': False, 'error': 'Instagram processing failed'}
    
    async def process_threads(self, url: str) -> Dict:
        """Process Threads URL"""
        try:
            file_path = await self.download_media(url, platform='threads')
            
            if file_path:
                return {
                    'success': True,
                    'type': 'direct_download',
                    'file_path': file_path,
                    'title': 'Threads Content',
                    'media_type': 'Video/Image'
                }
            else:
                return {'success': False, 'error': 'Threads download failed'}
                
        except Exception as e:
            logger.error(f"Threads processing error: {e}")
            return {'success': False, 'error': 'Threads processing failed'}
    
    async def process_youtube(self, url: str) -> Dict:
        """Process YouTube URL"""
        try:
            info = await self.get_media_info(url)
            
            if info:
                # Cache the info
                url_hash = self.get_url_hash(url)
                self.download_cache[url_hash] = info
                
                return {'success': True, 'type': 'menu', 'info': info}
            else:
                return {'success': False, 'error': 'Could not extract YouTube info'}
                
        except Exception as e:
            logger.error(f"YouTube processing error: {e}")
            return {'success': False, 'error': 'YouTube processing failed'}
    
    async def process_generic(self, url: str, platform: str) -> Dict:
        """Process generic platform URL"""
        try:
            info = await self.get_media_info(url)
            
            if info:
                return {'success': True, 'type': 'menu', 'info': info}
            else:
                # Try direct download
                file_path = await self.download_media(url, platform=platform)
                
                if file_path:
                    return {
                        'success': True,
                        'type': 'direct_download',
                        'file_path': file_path,
                        'title': f'{platform.title()} Content',
                        'media_type': 'Video/Audio'
                    }
                else:
                    return {'success': False, 'error': f'{platform.title()} download failed'}
                    
        except Exception as e:
            logger.error(f"Generic processing error: {e}")
            return {'success': False, 'error': 'Processing failed'}
    
    async def download_media(self, url: str, quality: str = None, audio_only: bool = False, platform: str = None) -> Dict:
        """Download media and return result"""
        try:
            # Detect platform if not provided
            if not platform:
                platform = self.detect_platform(url)
            
            logger.info(f"📥 Starting download: {platform} - Quality: {quality if quality else 'audio' if audio_only else 'auto'}")
            
            file_path = await self.download_media_file(url, quality, audio_only, platform)
            
            if file_path and os.path.exists(file_path):
                # Determine media type
                if audio_only:
                    media_type = "MP3 Audio"
                elif quality:
                    media_type = f"{quality} Video"
                else:
                    media_type = "Video/Audio"
                
                logger.info(f"✅ Download successful: {file_path}")
                
                return {
                    'success': True,
                    'file_path': file_path,
                    'title': self.extract_title_from_path(file_path),
                    'media_type': media_type
                }
            else:
                logger.error(f"❌ Download failed: No file created")
                return {'success': False, 'error': 'Download failed - no file created'}
                
        except Exception as e:
            logger.error(f"❌ Download error: {e}")
            return {'success': False, 'error': f'Download failed: {str(e)}'}
    
    async def download_media_file(self, url: str, quality: str = None, audio_only: bool = False, platform: str = None) -> Optional[str]:
        """Download media file using yt-dlp"""
        try:
            temp_dir = tempfile.mkdtemp(dir=TEMP_DIR)
            filename = f"{self.get_url_hash(url)[:8]}_{int(time.time())}"
            
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
            else:
                output_template = os.path.join(temp_dir, f"{filename}.%(ext)s")
                format_selector = self.video_qualities.get(quality, 'best[ext=mp4]/best')
                
                ydl_opts = {
                    'format': format_selector,
                    'outtmpl': output_template,
                    'quiet': True,
                    'no_warnings': True,
                    'merge_output_format': 'mp4',
                    'noplaylist': True
                }
            
            # Add platform-specific options
            if platform == 'youtube' and os.path.exists(YOUTUBE_COOKIES_FILE):
                ydl_opts['cookiefile'] = YOUTUBE_COOKIES_FILE
            elif platform in ['instagram', 'threads']:
                ydl_opts = self.instagram_auth.get_ytdl_opts(ydl_opts)
            
            # Enhanced settings
            ydl_opts.update({
                'retries': 2,
                'socket_timeout': 20,
                'http_chunk_size': 16777216,
                'concurrent_fragment_downloads': 6
            })
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Find downloaded file
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path) and file.startswith(filename):
                    return file_path
            
            return None
            
        except Exception as e:
            logger.error(f"Download failed: {e}")
            return None
    
    async def download_media_with_filename(self, url: str, filename: str = None, audio_only: bool = False) -> Optional[str]:
        """Download media with custom filename"""
        try:
            temp_dir = tempfile.mkdtemp(dir=TEMP_DIR)
            
            if filename:
                safe_filename = self.sanitize_filename(filename)
            else:
                safe_filename = f"media_{int(time.time())}"
            
            if audio_only:
                output_template = os.path.join(temp_dir, f"{safe_filename}.%(ext)s")
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
            else:
                output_template = os.path.join(temp_dir, f"{safe_filename}.%(ext)s")
                ydl_opts = {
                    'format': 'best[ext=mp4]/best',
                    'outtmpl': output_template,
                    'quiet': True,
                    'no_warnings': True,
                    'merge_output_format': 'mp4',
                    'noplaylist': True
                }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Find downloaded file
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                if os.path.isfile(file_path) and file.startswith(safe_filename):
                    return file_path
            
            return None
            
        except Exception as e:
            logger.error(f"Download with filename failed: {e}")
            return None
    
    async def get_media_info(self, url: str) -> Optional[Dict]:
        """Extract media information"""
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
            
            # Add YouTube cookies if available
            if 'youtube' in url and os.path.exists(YOUTUBE_COOKIES_FILE):
                ydl_opts['cookiefile'] = YOUTUBE_COOKIES_FILE
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                return {
                    'title': info.get('title', 'Unknown Title'),
                    'duration': info.get('duration', 0),
                    'thumbnail': info.get('thumbnail'),
                    'uploader': info.get('uploader', 'Unknown'),
                    'id': info.get('id', ''),
                    'platform': self.detect_platform(url),
                    'timestamp': time.time()
                }
                
        except Exception as e:
            logger.warning(f"Media info extraction failed: {e}")
            return None
    
    async def extract_spotify_metadata(self, url: str) -> Optional[Dict]:
        """Extract Spotify metadata"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=12)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, 'html.parser')
            title_tag = soup.find('meta', property='og:title')
            
            if not title_tag:
                return None
            
            title_text = title_tag.get('content', '')
            
            # Parse track info
            if '/track/' in url.lower():
                if ' • ' in title_text:
                    track_name, artist = title_text.split(' • ', 1)
                elif ' - ' in title_text:
                    artist, track_name = title_text.split(' - ', 1)
                else:
                    track_name = title_text
                    artist = ""
                
                search_query = f"ytsearch1:{track_name} {artist}" if artist else f"ytsearch1:{track_name}"
                filename = f"{artist} - {track_name}" if artist else track_name
                full_title = filename
                
            elif '/artist/' in url.lower():
                artist = title_text
                search_query = f"ytsearch1:best song {artist}"
                filename = f"{artist} - Best Of"
                full_title = filename
                
            else:
                return None
            
            return {
                'search_query': search_query,
                'filename': filename,
                'full_title': full_title
            }
            
        except Exception as e:
            logger.error(f"Spotify metadata extraction error: {e}")
            return None
    
    def extract_title_from_path(self, file_path: str) -> str:
        """Extract title from file path"""
        try:
            filename = os.path.basename(file_path)
            title = os.path.splitext(filename)[0]
            return title
        except:
            return "Downloaded Media"
    
    async def generate_qr_code(self, data: str) -> Optional[str]:
        """Generate QR code with embedded text"""
        try:
            # Create QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_H,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGB")

            # High Resolution upscale
            upscale = 6
            img_qr = img_qr.resize((img_qr.size[0] * upscale, img_qr.size[1] * upscale), Image.NEAREST)

            img_w, img_h = img_qr.size
            draw = ImageDraw.Draw(img_qr)

            # Font setup
            font_path = "../ShadowHand.ttf"
            try:
                font = ImageFont.truetype(font_path, int(img_w * 0.12))
            except:
                font = ImageFont.load_default()
                logger.warning("⚠️ ShadowHand.ttf font not found, using default font")

            text = "@abdifahadi"
            text_bbox = draw.textbbox((0, 0), text, font=font)
            text_w, text_h = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
            
            # Scale down font if text is too wide
            while text_w > img_w * 0.7:
                font_size = int(font.size * 0.9) if hasattr(font, 'size') else max(8, int(img_w * 0.10))
                try:
                    font = ImageFont.truetype(font_path, font_size)
                except:
                    font = ImageFont.load_default()
                    break
                text_bbox = draw.textbbox((0, 0), text, font=font)
                text_w, text_h = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]

            # Center position
            x = (img_w - text_w) // 2
            y = (img_h - text_h) // 2

            # White background for readability
            padding = int(0.05 * text_h)
            draw.rectangle(
                [(x - padding, y - padding), (x + text_w + padding, y + text_h + padding)],
                fill="white"
            )

            # Draw text
            draw.text((x, y), text, font=font, fill="black")

            # Final downscale for smoothness
            final_img = img_qr.resize((img_w // upscale, img_h // upscale), Image.LANCZOS)

            # Save to temp file
            timestamp = int(time.time())
            file_path = f"{TEMP_DIR}/qr_output_{timestamp}.png"
            final_img.save(file_path)
            return file_path

        except Exception as e:
            logger.error(f"❌ QR generation failed: {e}")
            return None


class InstagramCookieManager:
    """Manages Instagram cookies for authentication"""
    
    def __init__(self, cookies_file: str = INSTAGRAM_COOKIES_FILE):
        self.cookies_file = cookies_file
        self.cookies = {}
        self.session_cookies = None
        self.proxy_config = None
        self.last_request_time = 0
        self._setup_proxy()
        self._load_cookies()
    
    def _setup_proxy(self):
        """Setup proxy configuration"""
        if PROXY_HOST and PROXY_PORT and PROXY_HOST.strip() and PROXY_PORT.strip():
            try:
                proxy_url = f"http://{PROXY_HOST}:{PROXY_PORT}"
                if PROXY_USER and PROXY_PASS and PROXY_USER.strip() and PROXY_PASS.strip():
                    proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
                
                self.proxy_config = {
                    'http': proxy_url,
                    'https': proxy_url
                }
                logger.info(f"✅ Proxy configured")
            except Exception as e:
                logger.warning(f"❌ Proxy configuration failed: {e}")
                self.proxy_config = None
        else:
            self.proxy_config = None
    
    def _load_cookies(self):
        """Load cookies from file"""
        try:
            if not os.path.exists(self.cookies_file):
                logger.warning(f"❌ Instagram cookies file not found: {self.cookies_file}")
                return
            
            self.cookies = {}
            with open(self.cookies_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or (line.startswith('#') and not line.startswith('#HttpOnly_')):
                        continue
                    
                    if line.startswith('#HttpOnly_'):
                        line = line[10:]
                    
                    parts = line.split('\t')
                    if len(parts) >= 7:
                        domain = parts[0]
                        name = parts[5]
                        value = parts[6]
                        
                        if '.instagram.com' in domain:
                            self.cookies[name] = value
            
            self.session_cookies = requests.cookies.RequestsCookieJar()
            for name, value in self.cookies.items():
                self.session_cookies.set(name, value, domain='.instagram.com')
            
            logger.info(f"✅ Loaded {len(self.cookies)} Instagram cookies")
            
        except Exception as e:
            logger.error(f"❌ Failed to load Instagram cookies: {e}")
            self.cookies = {}
            self.session_cookies = None
    
    def get_ytdl_opts(self, base_opts: Dict = None) -> Dict:
        """Get yt-dlp options with Instagram authentication"""
        opts = base_opts.copy() if base_opts else {}
        
        if os.path.exists(self.cookies_file):
            opts['cookiefile'] = self.cookies_file
            logger.info(f"🍪 Using cookies file: {self.cookies_file}")
        
        if self.proxy_config:
            opts['proxy'] = self.proxy_config.get('https', self.proxy_config.get('http'))
        
        return opts