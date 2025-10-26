# WhatsApp Media Downloader Bot

A powerful WhatsApp bot that can download media from various platforms including YouTube, Instagram, TikTok, Spotify, Twitter, Facebook, Pinterest, and more.

## Features

- 🎬 Download videos from YouTube, Instagram, TikTok, Twitter, Facebook, Pinterest
- 🎵 Convert YouTube and Spotify tracks to MP3 (320kbps)
- 📷 Download images from social media platforms
- 📱 No watermarks on downloaded content
- ⚡ Lightning-fast downloads with smart fallback mechanisms
- 🔐 Instagram authentication support for private content access
- 🌐 Proxy support for Instagram requests
- 📲 QR code generation

## Supported Platforms

- YouTube (Video & Audio)
- Instagram (Reels, Posts, Stories, Images)
- TikTok (Videos without watermark)
- Spotify (Auto MP3 conversion)
- Twitter/X (Videos, GIFs, Images)
- Facebook (Videos, Posts, Images)
- Pinterest (Videos, Images)
- Threads (Videos, Images)

## Prerequisites

1. Python 3.8 or higher
2. FFmpeg (for audio/video processing)
3. WhatsApp Business API access
4. Instagram cookies for Instagram downloads (optional but recommended)

## Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Whatsapp\ Version
```

2. Install the required packages:
```bash
pip install -r requirements.txt
```

3. Install FFmpeg:
   - Windows: Download from https://ffmpeg.org/download.html
   - macOS: `brew install ffmpeg`
   - Linux: `sudo apt install ffmpeg`

## Configuration

1. Update the `.env` file with your WhatsApp API credentials:
   - `PHONE_NUMBER_ID`: Your WhatsApp Business phone number ID
   - `WHATSAPP_TOKEN`: Your WhatsApp API token
   - `VERIFY_TOKEN`: Verification token for webhook
   - `YOUTUBE_API_KEY`: YouTube API key (optional)
   - `YOUTUBE_CHANNEL_ID`: YouTube channel ID for notifications (optional)
   - `PROXY_HOST`, `PROXY_PORT`, `PROXY_USER`, `PROXY_PASS`: Proxy settings for Instagram (optional)

2. For Instagram downloads, add your Instagram cookies to `cookies.txt` in Netscape format.

3. For YouTube downloads with cookies (to bypass rate limits), add YouTube cookies to `ytcookies.txt` in Netscape format.

## Running the Bot

Start the bot with:
```bash
python whatsapp_bot.py
```

The bot will start a web server on port 8080 (or the port specified in your .env file).

## Setting up Webhook

Configure your WhatsApp Business API webhook to point to:
```
https://your-domain.com/webhook
```

Make sure to use the VERIFY_TOKEN you specified in your .env file.

## Usage

1. Send `/start` to the bot to see available options
2. Send any supported URL to download the content
3. For YouTube videos, you'll get quality options to choose from
4. For other platforms, you'll get video/audio options
5. Send any text to generate a QR code

## Commands

- `/start` - Show welcome message and options
- `/help` - Show help message with supported platforms
- `/qr` - Generate QR code from text
- Send any URL - Download media from that URL
- Send any text - Generate QR code

## Troubleshooting

1. **Instagram downloads failing**: Make sure your cookies.txt file contains valid Instagram session cookies.
2. **Large files not sending**: WhatsApp has a 50MB limit for media files.
3. **Download errors**: Try sending the URL again or check if the content is private/restricted.

## License

This project is licensed under the MIT License.