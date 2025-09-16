# WhatsApp Bot Configuration
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# WhatsApp Cloud API Settings
WHATSAPP_TOKEN = os.getenv('WHATSAPP_TOKEN', 'EAAPu3LSkZATwBPWHzw2WyX0I0og5tWrvR7BE0uMqQa4wCgu0amrsggZBteBuoZAbZAZA9Nv7IOZBUaEK21BqeFZABWZCUYU4SS8mmbMGwjahjBlQ3afw5AkX7uTZAI24zBaPPxkD3TleDHVQJgV6D6FCbl0xKTk1q9834j6Fw5mAZAZCvmT42LIbE1fHZAgJa1bb0QZDZD')
VERIFY_TOKEN = os.getenv('VERIFY_TOKEN', 'abdifahadi-whatsapp')
PHONE_NUMBER_ID = os.getenv('PHONE_NUMBER_ID', '776479612214195')
WABA_ID = os.getenv('WABA_ID', '1418378945931807')

# YouTube API Settings
YOUTUBE_API_KEY = os.getenv('YOUTUBE_API_KEY', 'AIzaSyCceitig_f7_6qZWxrat1qrRGU2jzvKMj4')
YOUTUBE_CHANNEL_ID = os.getenv('YOUTUBE_CHANNEL_ID', 'UCOL7qS5ZDIPlRCFe04JWPCg')
YOUTUBE_CHECK_INTERVAL = int(os.getenv('YOUTUBE_CHECK_INTERVAL', 600))  # 10 minutes

# Instagram Settings
INSTAGRAM_COOKIES_FILE = "cookies.txt"
INSTAGRAM_REQUEST_DELAY = int(os.getenv('INSTAGRAM_REQUEST_DELAY', 4))

# YouTube Settings
YOUTUBE_COOKIES_FILE = "ytcookies.txt"

# Proxy Settings (optional)
PROXY_HOST = os.getenv('PROXY_HOST', '')
PROXY_PORT = os.getenv('PROXY_PORT', '')
PROXY_USER = os.getenv('PROXY_USER', '')
PROXY_PASS = os.getenv('PROXY_PASS', '')

# File Size Limits
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB (WhatsApp/Telegram limit)
WHATSAPP_MAX_BYTES = int(os.getenv('WHATSAPP_MAX_BYTES', 95 * 1024 * 1024))  # 95MB WhatsApp file limit

# Directory Settings
DOWNLOADS_DIR = "downloads"
TEMP_DIR = "temp"
DATA_DIR = "data"

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
    'pinterest.com', 'pin.it',
    'threads.net'
]

# Cache Settings
CACHE_DURATION = 3600  # 1 hour
CLEANUP_INTERVAL = 900  # 15 minutes
FILE_CLEANUP_AGE = 900  # 15 minutes

# Developer Info
DEVELOPER_INFO = {
    'name': 'Abdi Fahadi',
    'version': '1.0',
    'help_url': 'https://abdifahadi.carrd.co'
}

# WhatsApp API Configuration
WHATSAPP_API_BASE_URL = f"https://graph.facebook.com/v18.0/{PHONE_NUMBER_ID}"
WHATSAPP_MEDIA_URL = f"{WHATSAPP_API_BASE_URL}/media"
WHATSAPP_MESSAGES_URL = f"{WHATSAPP_API_BASE_URL}/messages"