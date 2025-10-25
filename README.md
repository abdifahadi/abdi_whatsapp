# Ultra-Fast Media Downloader - WhatsApp Version

This is a WhatsApp bot that can download media from various social platforms including YouTube, Instagram, TikTok, Spotify, Twitter, and Facebook.

## Features

- 🚀 Ultra-fast media downloading
- 🎬 Video download (up to 1080p)
- 🎵 Audio download (320kbps MP3)
- 📸 Image download
- 📱 Support for all major social platforms
- 🔄 Smart content detection
- 📤 Direct file sending via WhatsApp

## Supported Platforms

- YouTube (Video & Audio)
- Instagram (Reels, Posts, Stories)
- TikTok (Videos)
- Spotify (Music - Auto MP3 conversion)
- Twitter/X (Videos, GIFs, Images)
- Facebook (Videos, Posts, Images)
- Pinterest (Videos, Images)

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file with your WhatsApp Business API credentials:

```env
PHONE_NUMBER_ID="your_phone_number_id"
WHATSAPP_TOKEN="your_whatsapp_access_token"
VERIFY_TOKEN="your_verification_token"
```

### 3. Configure Instagram Cookies (Optional but Recommended)

For Instagram downloads to work properly:
1. Create a `cookies.txt` file in the project root
2. Extract your Instagram session cookies using a browser extension like "Cookie-Editor"
3. Save in Netscape format

### 4. Run the Bot

```bash
python app.py
```

## Webhook Configuration

To receive messages from WhatsApp, you need to set up a webhook URL:
1. Deploy this application to a public server
2. Configure your WhatsApp Business API webhook to point to your server's URL
3. Ensure the VERIFY_TOKEN matches in both your .env file and WhatsApp configuration

## Testing

To test the bot functionality, you can run:

```bash
python whatsapp_bot_simple.py
```

This will simulate the bot processing an Instagram reel URL as requested.

## How It Works

1. User sends a social media link to the WhatsApp bot
2. Bot detects the platform and content type
3. Bot downloads the media using appropriate methods:
   - yt-dlp for YouTube, TikTok, etc.
   - Instaloader for Instagram with authentication
   - Custom scrapers for other platforms
4. Bot sends the downloaded media back to the user

## Example Usage

For the Instagram reel URL: `https://www.instagram.com/reel/DL452nITuB3`

The bot will:
1. Show processing messages
2. Display the video title and creator username
3. Download the video
4. Send the video file back to the user

## Project Structure

```
Whatsapp Version/
├── .env                 # Environment variables
├── app.py              # Flask webhook server
├── config.py           # Configuration settings
├── cookies.txt         # Instagram cookies (optional)
├── requirements.txt    # Python dependencies
├── whatsapp_bot_simple.py  # Main bot logic
├── ytcookies.txt       # YouTube cookies (optional)
└── README.md           # This file
```

## Deployment

For production deployment, you can use:
- Heroku
- AWS Elastic Beanstalk
- Google Cloud Run
- Any cloud platform that supports Python web applications

Make sure your deployment platform supports:
- Python 3.8+
- Outbound internet access for downloading media
- Inbound webhook access from Facebook/WhatsApp

## Troubleshooting

### Instagram Downloads Not Working
1. Ensure you have a valid `cookies.txt` file
2. Check that your Instagram session is active
3. Verify the cookies are in Netscape format

### YouTube Downloads Slow
1. Add a `ytcookies.txt` file with YouTube cookies
2. This helps bypass rate limits and bot detection

### File Size Limits
WhatsApp has a 50MB file size limit for media files. The bot will automatically reject larger files.

## License

This project is for personal use only. Do not use for commercial purposes without permission.