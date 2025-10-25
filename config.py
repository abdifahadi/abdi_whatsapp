# Ultra-Fast Media Downloader Bot Configuration
import os

# Bot Settings
BOT_TOKEN = "8282662575:AAE6TrZAc3YvnIx6LOJQHI1UdhxgvaUXVVA"  # Your bot token from @BotFather

# WhatsApp Settings
PHONE_NUMBER_ID = os.getenv('PHONE_NUMBER_ID', '776479612214195')
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN', '')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'abdifahadi-whatsapp')
WABA_ID = os.getenv('WABA_ID', '')

# YouTube API Settings
YOUTUBE_API_KEY = "AIzaSyCceitig_f7_6qZWxrat1qrRGU2jzvKMj4"
YOUTUBE_CHANNEL_ID = "UCOL7qS5ZDIPlRCFe04JWPCg"
YOUTUBE_CHECK_INTERVAL = 600  # 10 minutes in seconds

# Instagram Settings
INSTAGRAM_COOKIES_FILE = "cookies.txt"  # Path to Instagram cookies file (Netscape format)
INSTAGRAM_REQUEST_DELAY = 4  # Delay between Instagram requests (seconds) - increased to reduce 403 errors

# YouTube Settings
# Path to YouTube cookies file (Netscape format)
YOUTUBE_COOKIES_FILE = "ytcookies.txt"

# Proxy Settings (optional - for Instagram requests)
PROXY_HOST = os.getenv('PROXY_HOST', '')  # Residential proxy host
PROXY_PORT = os.getenv('PROXY_PORT', '')  # Proxy port
PROXY_USER = os.getenv('PROXY_USER', '')  # Proxy username
PROXY_PASS = os.getenv('PROXY_PASS', '')  # Proxy password

# File Size Limits
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB in bytes (Telegram limit)

# Directory Settings
DOWNLOADS_DIR = "downloads"
TEMP_DIR = "temp"
DATA_DIR = "data"  # For storing persistent data like last video ID

# Quality Settings
AUDIO_BITRATE = "320"  # kbps for MP3 downloads

# Supported Platforms
SUPPORTED_PLATFORMS = [
    'youtube.com', 'youtu.be', 'music.youtube.com',
    'instagram.com', 'instagr.am',
    'tiktok.com', 'vm.tiktok.com',
    'twitter.com', 'x.com', 't.co',
    'facebook.com', 'fb.watch', 'fb.me',
    'spotify.com', 'open.spotify.com',
    'pinterest.com', 'pin.it'
]

# Cache Settings
CACHE_DURATION = 3600  # 1 hour in seconds (reduced for better performance)
CLEANUP_INTERVAL = 900  # 15 minutes in seconds (reduced for faster cleanup)
FILE_CLEANUP_AGE = 900  # 15 minutes in seconds (reduced for faster cleanup)

# Developer Info
DEVELOPER_INFO = {
    'name': 'Abdi Fahadi',
    'version': '1.0',
    'help_url': 'https://abdifahadi.carrd.co'
}
