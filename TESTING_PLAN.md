# WhatsApp Bot Testing Plan

This document outlines the testing plan for the WhatsApp Media Downloader Bot to ensure it works correctly with all supported platforms.

## Test URLs

The following URLs will be tested to verify the bot's functionality:

1. **YouTube Shorts**: https://www.youtube.com/shorts/4H-ckF9H_y0
2. **Instagram Reels**: https://www.instagram.com/reel/DLP0StQz1Tq/
3. **Instagram Video Post**: https://www.instagram.com/p/DGDfJ3LzdEL/
4. **Instagram Image Post**: https://www.instagram.com/p/DJeuZqsz5JT/
5. **Instagram Carousel Post**: https://www.instagram.com/p/DK_2g5CzKwQ/?img_index=1
6. **TikTok Video**: https://vt.tiktok.com/ZSUKPdCtm
7. **Spotify Track**: https://open.spotify.com/track/5cmZe5DxE3uicDwfe24ls6?si=58d5dcb261584e62

## Prerequisites for Testing

1. **Cookies Files**:
   - `cookies.txt` - Instagram session cookies in Netscape format
   - `ytcookies.txt` - YouTube session cookies in Netscape format

2. **Dependencies**:
   - Python 3.8+
   - FFmpeg
   - All packages in `requirements.txt`

## Test Scripts

### 1. Cookie Validation Script
```bash
python check_cookies.py
```
This script verifies that the cookies files exist and contain the necessary session cookies.

### 2. Download Test Script
```bash
python test_downloads.py
```
This script tests downloading from all supported platforms and saves the files to a `test_downloads` directory.

## Expected Results

### Successful Tests
- All downloads should complete without errors
- Files should be saved with appropriate names and extensions
- Video files should be playable
- Audio files should be playable
- Image files should be viewable

### Platform-Specific Expectations

1. **YouTube Shorts**: Should download as MP4 video
2. **Instagram Reels**: Should download as MP4 video
3. **Instagram Video Post**: Should download as MP4 video
4. **Instagram Image Post**: Should download as JPG/PNG image
5. **Instagram Carousel Post**: Should download all images/videos in the post
6. **TikTok Video**: Should download as MP4 video without watermark
7. **Spotify Track**: Should download as MP3 audio (320kbps)

## Troubleshooting

### Common Issues and Solutions

1. **Instagram Downloads Failing**:
   - Check that `cookies.txt` contains valid session cookies
   - Ensure `sessionid` and `ds_user_id` cookies are present
   - Verify cookies are in Netscape format

2. **YouTube Downloads Failing**:
   - Check that `ytcookies.txt` contains valid session cookies
   - Verify cookies are in Netscape format

3. **Large Files Not Downloading**:
   - WhatsApp has a 50MB limit for media files
   - Try selecting a lower quality option

4. **Rate Limiting Errors**:
   - Wait a few minutes before trying again
   - Use proxy settings if available

## Testing Process

1. Run the cookie validation script first
2. Run the download test script
3. Verify all downloaded files
4. Check logs for any errors or warnings
5. Fix any issues and retest

## Deployment Verification

After successful local testing, the bot should be deployed to Railway and tested with actual WhatsApp messages to ensure the webhook integration works correctly.