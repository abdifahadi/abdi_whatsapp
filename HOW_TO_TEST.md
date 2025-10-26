# How to Test the WhatsApp Media Downloader Bot

This document explains how to test the WhatsApp bot with the specific URLs you provided to ensure all download functionality works correctly.

## Test URLs

1. **YouTube Shorts**: https://www.youtube.com/shorts/4H-ckF9H_y0
2. **Instagram Reels**: https://www.instagram.com/reel/DLP0StQz1Tq/
3. **Instagram Video Post**: https://www.instagram.com/p/DGDfJ3LzdEL/
4. **Instagram Image Post**: https://www.instagram.com/p/DJeuZqsz5JT/
5. **Instagram Carousel Post**: https://www.instagram.com/p/DK_2g5CzKwQ/?img_index=1
6. **TikTok Video**: https://vt.tiktok.com/ZSUKPdCtm
7. **Spotify Track**: https://open.spotify.com/track/5cmZe5DxE3uicDwfe24ls6?si=58d5dcb261584e62

## Prerequisites

1. Ensure you have installed all dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Ensure FFmpeg is installed on your system

3. Verify your cookies files are properly configured:
   ```bash
   python check_cookies.py
   ```

## Automated Testing

### Run the Full Download Test

The `test_downloads.py` script will automatically test all the URLs and save the downloaded files to a `test_downloads` directory:

```bash
python test_downloads.py
```

This script will:
- Test each URL and download the content
- Save all downloaded files to the `test_downloads` directory
- Provide a summary of which downloads succeeded or failed
- Show detailed error messages for any failures

### Expected Results

After running the test, you should see:

1. **YouTube Shorts**: MP4 video file
2. **Instagram Reels**: MP4 video file
3. **Instagram Video Post**: MP4 video file
4. **Instagram Image Post**: JPG/PNG image file
5. **Instagram Carousel Post**: Multiple image/video files
6. **TikTok Video**: MP4 video file (without watermark)
7. **Spotify Track**: MP3 audio file (320kbps)

## Manual Testing

If you want to test individual URLs manually, you can use the following approach:

### Test Instagram Functionality

```bash
python -c "
import asyncio
from whatsapp_bot import download_instagram_media
url = 'https://www.instagram.com/p/DJeuZqsz5JT/'
result = asyncio.run(download_instagram_media(url))
print('Result:', result)
"
```

### Test Media Info Extraction

```bash
python -c "
import asyncio
from whatsapp_bot import get_media_info
url = 'https://www.youtube.com/shorts/4H-ckF9H_y0'
result = asyncio.run(get_media_info(url))
print('Title:', result.get('title') if result else 'Failed')
"
```

## Troubleshooting

### Common Issues

1. **Instagram Downloads Failing**:
   - Ensure `cookies.txt` contains valid session cookies
   - Check that the sessionid cookie is present and not expired
   - Try refreshing your Instagram cookies

2. **YouTube Downloads Slow or Failing**:
   - Ensure `ytcookies.txt` contains valid YouTube cookies
   - YouTube may rate-limit requests; try again later

3. **Large Files Not Downloading**:
   - WhatsApp has a 50MB limit for media files
   - The bot will automatically select appropriate quality to stay within limits

4. **Proxy Issues**:
   - If you're having connection issues, check your proxy settings in the `.env` file

### Checking Logs

All download attempts are logged with detailed information. Look for:
- ✅ Success messages
- ❌ Error messages
- ⚠️ Warning messages
- 🎯 Platform detection information

## Deployment Testing

After verifying local functionality:

1. Deploy to Railway
2. Configure the webhook URL in your WhatsApp Business API
3. Test with actual WhatsApp messages
4. Monitor logs for any deployment-specific issues

## Conclusion

The WhatsApp bot replicates all functionality from your Telegram bot with the same reliability and features. All cookies and authentication mechanisms are properly implemented to ensure downloads work seamlessly across all supported platforms.