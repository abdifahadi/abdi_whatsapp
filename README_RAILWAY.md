# WhatsApp Bot for Railway Deployment

This is a production-ready WhatsApp bot that can be deployed on Railway with all necessary configurations.

## Deployment Instructions

1. **Create a new Railway project**
   - Go to https://railway.app/
   - Create a new project
   - Connect your GitHub repository or upload the files

2. **Set Environment Variables**
   The following environment variables need to be set in Railway:
   ```
   PHONE_NUMBER_ID=your_phone_number_id
   WHATSAPP_TOKEN=your_whatsapp_token
   VERIFY_TOKEN=your_verify_token
   WABA_ID=your_business_account_id
   PORT=8080
   ```

3. **Deployment Files**
   - `Dockerfile` - Defines the container image
   - `Procfile` - Specifies the start command
   - `nixpacks.toml` - Alternative deployment configuration
   - `requirements.txt` - Python dependencies

4. **Required Files**
   - `.env` - Environment variables (not committed to git for security)
   - `cookies.txt` - Instagram cookies for authentication
   - `ytcookies.txt` - YouTube cookies for authentication

## Features

- ✅ Instagram reel download with proper title and creator extraction
- ✅ YouTube video download
- ✅ TikTok video download
- ✅ Twitter video download
- ✅ Facebook video download
- ✅ Spotify audio download
- ✅ Proxy support for bypassing geo-restrictions
- ✅ Cookie-based authentication for Instagram and YouTube

## How It Works

1. Users send a media link (Instagram, YouTube, etc.) to the WhatsApp bot
2. The bot extracts the title and creator information
3. The bot downloads the media file
4. The bot sends the downloaded file back to the user

## Instagram Authentication

For Instagram downloads to work properly:
1. Update `cookies.txt` with fresh Instagram session cookies
2. Make sure the cookies include `sessionid` and `ds_user_id`
3. Cookies should be in Netscape format

## YouTube Authentication

For YouTube downloads to work with age-restricted content:
1. Update `ytcookies.txt` with YouTube session cookies
2. Log into YouTube in your browser and export cookies

## Proxy Configuration

If you need to use a proxy:
1. Set the following environment variables:
   ```
   PROXY_HOST=your_proxy_host
   PROXY_PORT=your_proxy_port
   PROXY_USER=your_proxy_user
   PROXY_PASS=your_proxy_password
   ```

## Testing

To test the bot locally:
```bash
python whatsapp_bot_production.py
```

## Support

For issues with deployment or functionality, check the logs in Railway for error messages.