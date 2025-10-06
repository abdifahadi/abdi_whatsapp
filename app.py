"""
Abdi WhatsApp Bot - FastAPI Implementation
A WhatsApp bot with media downloading and QR code generation features
Compatible with Railway deployment
"""

import os
import logging
import json
import asyncio
from typing import Optional
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
import uvicorn
import aiohttp

# Import configuration
from qr_generator import qr_generator
from store import session_manager
from media_processor import MediaProcessor
from whatsapp_sender import WhatsAppSender
from config import (
    VERIFY_TOKEN, WHATSAPP_TOKEN, PHONE_NUMBER_ID, WABA_ID,
    WHATSAPP_MESSAGES_URL, DEVELOPER_INFO, WHATSAPP_API_BASE_URL
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global session for HTTP requests
session = None

# Initialize processors
media_processor = MediaProcessor()
whatsapp_sender = WhatsAppSender()

async def get_session():
    """Get aiohttp session"""
    global session
    if session is None:
        session = aiohttp.ClientSession()
    return session

async def send_whatsapp_message(phone_number: str, message_text: str):
    """Send a text message via WhatsApp Cloud API"""
    try:
        session = await get_session()
        
        headers = {
            'Authorization': f'Bearer {WHATSAPP_TOKEN}',
            'Content-Type': 'application/json'
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "text",
            "text": {
                "body": message_text
            }
        }
        
        logger.info(f"📤 Sending message to {phone_number}: {message_text[:50]}...")
        
        async with session.post(WHATSAPP_MESSAGES_URL, headers=headers, json=payload) as response:
            if response.status == 200:
                result = await response.json()
                logger.info(f"✅ Message sent successfully: {result}")
                return True
            else:
                error_text = await response.text()
                logger.error(f"❌ Failed to send message: {response.status} - {error_text}")
                return False
                
    except Exception as e:
        logger.error(f"❌ Exception sending message: {e}")
        return False

async def process_text_message(phone_number: str, message_text: str, contact_name: str):
    """Process incoming text messages and send appropriate responses"""
    message_text = message_text.strip().lower()
    
    # Command responses (identical to Telegram bot)
    if message_text in ['start', '/start', 'hello', 'hi', 'menu']:
        response = f"""🚀 Welcome to Abdi WhatsApp Bot! Hello {contact_name}! 👋

*🚀 Ultra-Fast Media Downloader*

Download from *YouTube*, *Instagram*, *TikTok*, *Spotify*, *Twitter*, *Facebook*, *Pinterest* and more!

✨ *Features:*
• HD Video Quality (up to 1080p)
• High-Quality Audio (320kbps)
• Image & Post Download
• No Watermarks
• Lightning Fast Download
• Smart Content Detection
• Auto-Format Selection

Choose an option below to get started! 👇

*Quick Commands:*
📥 Type *"download"* to start downloading
📲 Type *"qr"* for QR code generation
ℹ️ Type *"about"* for more info
🔔 Type *"subscribe"* for my channel

*Just send any link to get started!* ✨"""
        
    elif message_text in ['help', '/help']:
        response = """💡 *Help & Documentation*

For detailed help and tutorials, visit:
🔗 https://abdifahadi.carrd.co

*Quick Commands:*
• *"start"* - Main menu
• *"download"* - Download instructions
• *"qr"* - QR code generator
• *"about"* - About me
• *"subscribe"* - My YouTube channel

*Just send a link to get started!* 🚀

Developed by @abdifahadi ✨"""
        
    elif message_text in ['download', '/download']:
        response = """*📥 Send Your Link*

*Supported Platforms:*
🎬 *YouTube* - Video & Audio (all qualities)
📱 *Instagram* - Reels, Posts, Stories & Images
🎵 *Spotify* - Music (Auto MP3 conversion)
🎪 *TikTok* - Videos without watermark
🐦 *Twitter/X* - Videos, GIFs & Images
📘 *Facebook* - Videos, Posts & Images
📌 *Pinterest* - Videos & Images

*Just send any link and I'll handle the rest automatically!* ✨"""
        
    elif message_text in ['qr', '/qr', 'qr code']:
        response = """*📲 QR Code Generator*

Send me any text or link and I will generate a QR code for you.

✨ *Features:*
• High-quality QR codes
• Custom branding with @abdifahadi
• Professional design
• Instant generation

Just send your text or link now! 📱"""
        
        # Set user in QR generation mode
        await session_manager.set_user_state(phone_number, 'qr')
        
    elif message_text in ['about', '/about']:
        response = """*I'm Abdi Fahadi — a curious mind juggling YouTube, coding, app creation, gaming, editing, and design. I create what I feel, when I feel — turning passion into pixels and ideas into reality.*

✨ *Stay connected — follow me on socials and join the journey!*

🔗 *My Links:*
📺 YouTube: https://abdi.oia.bio/fahadi
📸 Instagram: https://abdi.oia.bio/fahadi-insta
📘 Facebook: https://fb.openinapp.co/hb407
🎵 TikTok: https://tk.openinapp.link/abdifahadi
🐦 Twitter (X): https://x.openinapp.co/abdifahadi
🎮 Discord: https://dc.openinapp.co/abdifahadi

Type *"menu"* to go back to main menu."""
        
    elif message_text in ['subscribe', '/subscribe']:
        response = """🔔 *Subscribe to my channel for amazing content!*

📺 YouTube Channel: https://abdi.oia.bio/fahadi

Stay updated with:
• Tech tutorials
• App development
• Gaming content
• Creative projects
• And much more!

Type *"menu"* to go back to main menu."""
        
    elif message_text.startswith(('http://', 'https://')):
        # Process URL for download
        await process_url_download(phone_number, message_text, contact_name)
        return  # Don't send additional response
        
    else:
        response = f"""👋 Hello {contact_name}!

I received your message: "{message_text}"

💡 *Try these commands:*
• *start* - Main menu
• *help* - All commands  
• *download* - Download instructions
• *qr* - Generate QR codes

Or send any link for media download! 🚀"""
    
    # Send the response
    await send_whatsapp_message(phone_number, response)

async def generate_and_send_qr(phone_number: str, text: str):
    """Generate and send QR code with proper branding"""
    try:
        logger.info(f"🔄 Generating QR code for: {text[:50]}...")
        
        # Generate QR code using the QR generator
        qr_file_path = await qr_generator.generate_qr(text)
        
        if qr_file_path and os.path.exists(qr_file_path):
            logger.info(f"📤 Sending QR code image: {qr_file_path}")
            
            # Upload and send QR code image to WhatsApp
            success = await whatsapp_sender.send_media_file(
                phone_number=phone_number,
                file_path=qr_file_path,
                caption=f"📲 QR Code for: {text[:100]}{'...' if len(text) > 100 else ''}\n\n✨ Generated by @abdifahadi",
                media_type='image'
            )
            
            if success:
                logger.info(f"✅ QR code sent successfully to {phone_number}")
            else:
                logger.error(f"❌ Failed to send QR code to {phone_number}")
                # Fallback text message
                await send_whatsapp_message(phone_number, "❌ Failed to send QR code. Please try again.")
        else:
            logger.error(f"❌ QR code file not found: {qr_file_path}")
            await send_whatsapp_message(phone_number, "❌ Failed to generate QR code. Please try again.")
        
        # Clean up old QR files
        qr_generator.cleanup_old_qr_files()
        
    except Exception as e:
        logger.error(f"❌ QR generation and send failed: {e}")
        response = """❌ *QR Generation Failed*

Sorry, I couldn't generate your QR code right now. Please try again later.

Type *"menu"* to go back to main menu."""
        await send_whatsapp_message(phone_number, response)

async def process_quality_download(phone_number: str, url: str, quality: str, contact_name: str):
    """Process download with specific quality selection"""
    try:
        logger.info(f"🎬 Processing {quality} download for: {url}")
        
        # Send processing message
        quality_text = "Audio (MP3)" if quality == 'audio' else f"{quality} Video"
        await send_whatsapp_message(phone_number, f"🔄 *Downloading {quality_text}...*\n\n🚀 Please wait while I prepare your media.")
        
        # Download with specific quality
        audio_only = quality == 'audio'
        download_quality = quality if not audio_only else None
        
        result = await media_processor.download_media(url, download_quality, audio_only)
        
        if result.get('success'):
            file_path = result.get('file_path')
            if file_path and os.path.exists(file_path):
                logger.info(f"📤 Sending {quality} media: {file_path}")
                
                title = result.get('title', 'Downloaded Media')
                media_type = result.get('media_type', quality_text)
                
                platform_name = media_processor.detect_platform(url)
                platform_title = platform_name.title() if platform_name else "Unknown"
                
                # Upload and send media
                success = await whatsapp_sender.send_media_file(
                    phone_number=phone_number,
                    file_path=file_path,
                    caption=f"✨ *{title}*\n\n📱 {media_type}\n🔗 From: {platform_title}\n\n🚀 Downloaded by @abdifahadi bot",
                    media_type='auto'
                )
                
                if success:
                    logger.info(f"✅ Media sent successfully: {title} ({quality})")
                else:
                    logger.error(f"❌ Failed to send media: {title}")
                    await send_whatsapp_message(phone_number, "❌ Failed to send media file. Please try again.")
                
                # Clean up file after sending
                try:
                    os.remove(file_path)
                    logger.info(f"🗑️ Cleaned up file: {file_path}")
                except:
                    pass
            else:
                await send_whatsapp_message(phone_number, "❌ Download completed but file not found. Please try again.")
        else:
            error_msg = result.get('error', 'Unknown error')
            
            # Provide more helpful error messages
            if 'timeout' in error_msg.lower():
                error_response = "❌ *Download Timeout*\n\n⏰ The video is too large or connection is slow.\n\n💡 *Try:*\n• Lower quality (480p, 360p)\n• Audio only (MP3)\n• Check your internet connection"
            elif 'filesize' in error_msg.lower() or 'too large' in error_msg.lower():
                error_response = "❌ *File Too Large*\n\n📏 Video exceeds WhatsApp size limit (95MB).\n\n💡 *Try:*\n• Lower quality (480p, 360p)\n• Audio only (MP3)\n• Shorter video"
            elif 'unsupported' in error_msg.lower():
                error_response = "❌ *Unsupported Platform*\n\n🚫 This platform is not supported yet.\n\n✅ *Supported:*\nYouTube, Instagram, TikTok, Twitter, Facebook, Spotify, Pinterest"
            else:
                error_response = f"❌ *Download Failed*\n\nError: {error_msg}\n\n💡 *Try:*\n• Different quality\n• Audio only (MP3)\n• Check the link"
            
            await send_whatsapp_message(phone_number, error_response)
        
    except Exception as e:
        logger.error(f"❌ Quality download failed: {e}")
        await send_whatsapp_message(phone_number, f"❌ *Download Error*\n\nSomething went wrong while downloading.\n\nError: {str(e)[:100]}\n\nPlease try again.")

async def process_url_download(phone_number: str, url: str, contact_name: str):
    """Process URL for downloading and send media file"""
    try:
        logger.info(f"🔄 Processing download request from {phone_number}: {url}")
        
        # Send initial processing message
        await send_whatsapp_message(phone_number, f"🔄 *Processing your link...*\n\nURL: {url}\n\n🚀 Downloading media, please wait...")
        
        # Detect platform
        platform = media_processor.detect_platform(url)
        if not platform:
            await send_whatsapp_message(phone_number, "❌ *Unsupported Platform*\n\nSorry, this platform is not supported yet.\n\nSupported: YouTube, Instagram, TikTok, Twitter, Facebook, Spotify, Pinterest")
            return
        
        logger.info(f"🎯 Platform detected: {platform}")
        
        # Process URL based on platform
        result = await media_processor.process_url(url, platform)
        
        if not result.get('success'):
            error_msg = result.get('error', 'Unknown error')
            logger.error(f"❌ Processing failed: {error_msg}")
            
            # Provide more helpful error messages
            if 'timeout' in error_msg.lower():
                error_response = "❌ *Download Timeout*\n\n⏰ The video is too large or connection is slow.\n\n💡 *Try:*\n• Lower quality (480p, 360p)\n• Audio only (MP3)\n• Check your internet connection"
            elif 'filesize' in error_msg.lower() or 'too large' in error_msg.lower():
                error_response = "❌ *File Too Large*\n\n📏 Video exceeds WhatsApp size limit (95MB).\n\n💡 *Try:*\n• Lower quality (480p, 360p)\n• Audio only (MP3)\n• Shorter video"
            elif 'unsupported' in error_msg.lower():
                error_response = "❌ *Unsupported Platform*\n\n🚫 This platform is not supported yet.\n\n✅ *Supported:*\nYouTube, Instagram, TikTok, Twitter, Facebook, Spotify, Pinterest"
            else:
                error_response = f"❌ *Download Failed*\n\nError: {error_msg}\n\n💡 *Try:*\n• Different quality\n• Audio only (MP3)\n• Check the link"
            
            await send_whatsapp_message(phone_number, error_response)
            return
        
        # Handle different result types
        if result.get('type') == 'direct_download':
            # Direct download - send file immediately
            file_path = result.get('file_path')
            if file_path and os.path.exists(file_path):
                logger.info(f"📤 Sending media file: {file_path}")
                
                title = result.get('title', 'Downloaded Media')
                media_type = result.get('media_type', 'Media')
                
                # Upload and send media
                success = await whatsapp_sender.send_media_file(
                    phone_number=phone_number,
                    file_path=file_path,
                    caption=f"✨ *{title}*\n\n📱 {media_type}\n🔗 From: {platform.title()}\n\n🚀 Downloaded by @abdifahadi bot",
                    media_type='auto'
                )
                
                if success:
                    logger.info(f"✅ Media sent successfully: {title}")
                else:
                    logger.error(f"❌ Failed to send media: {title}")
                    await send_whatsapp_message(phone_number, "❌ Failed to send media file. Please try again.")
                
                # Clean up file after sending
                try:
                    os.remove(file_path)
                    logger.info(f"🗑️ Cleaned up file: {file_path}")
                except:
                    pass
            else:
                await send_whatsapp_message(phone_number, "❌ Download completed but file not found. Please try again.")
        
        elif result.get('type') == 'menu':
            # Show quality selection menu (for YouTube etc.)
            info = result.get('info', {})
            title = info.get('title', 'Media')
            duration = info.get('duration', 0)
            uploader = info.get('uploader', 'Unknown')
            
            # Format duration
            duration_str = ''
            if duration:
                minutes = duration // 60
                seconds = duration % 60
                duration_str = f" • {minutes}:{seconds:02d}"
            
            # Create quality selection message
            quality_text = f"✨ *{title}*\n\n📅 {uploader}{duration_str}\n🔗 {platform.title()}\n\n🎥 *Choose Quality:*\n\n🎬 **Video Options:**\n• 1080p HD (Best Quality)\n• 720p (Good Quality)\n• 480p (Standard)\n\n🎵 **Audio Only:**\n• MP3 320kbps (High Quality)\n\nReply with: **1080p**, **720p**, **480p**, or **mp3**"
            
            await send_whatsapp_message(phone_number, quality_text)
            
            # Set user in download mode with URL stored
            await session_manager.set_user_state(phone_number, 'download', {'url': url, 'info': info})
        
        else:
            await send_whatsapp_message(phone_number, "❌ Unexpected result format. Please try again.")
        
    except Exception as e:
        logger.error(f"❌ URL download processing failed: {e}")
        await send_whatsapp_message(phone_number, f"❌ *Download Error*\n\nSomething went wrong while processing your link.\n\nError: {str(e)[:100]}\n\nPlease try again.")

async def cleanup_session():
    """Cleanup aiohttp session"""
    global session
    if session:
        await session.close()
        session = None

# FastAPI app instance
app = FastAPI(
    title="Abdi WhatsApp Bot",
    description="WhatsApp bot with media downloading and QR code generation",
    version=DEVELOPER_INFO['version'],
    docs_url="/docs",
    redoc_url="/redoc"
)

@app.get("/")
async def root():
    """Root endpoint - Bot information"""
    return {
        "message": "🤖 Abdi WhatsApp Bot is running!",
        "status": "active",
        "version": DEVELOPER_INFO['version'],
        "developer": DEVELOPER_INFO['name'],
        "endpoints": {
            "webhook_verification": "/webhook (GET)",
            "webhook_messages": "/webhook (POST)",
            "health": "/health",
            "docs": "/docs"
        },
        "features": [
            "YouTube downloads",
            "Instagram downloads", 
            "TikTok downloads",
            "QR code generation",
            "Multi-platform support"
        ]
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "WhatsApp Bot",
        "verify_token_configured": bool(VERIFY_TOKEN),
        "whatsapp_token_configured": bool(WHATSAPP_TOKEN)
    }

@app.get("/webhook")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge")
):
    """
    WhatsApp webhook verification endpoint
    
    Meta will send a GET request with these query parameters:
    - hub.mode: should be "subscribe"
    - hub.verify_token: should match our VERIFY_TOKEN
    - hub.challenge: random string we need to return
    """
    logger.info(f"📞 Webhook verification request: mode={hub_mode}, token={hub_verify_token}, challenge={hub_challenge[:10] if hub_challenge else None}...")
    
    # Check if verification parameters are present
    if not hub_mode or not hub_verify_token or not hub_challenge:
        logger.error("❌ Missing verification parameters")
        raise HTTPException(
            status_code=400,
            detail={"error": "Missing verification parameters"}
        )
    
    # Verify the token and mode
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        logger.info(f"✅ Webhook verification successful, returning challenge: {hub_challenge}")
        # Return the challenge as plain text (required by Meta)
        return PlainTextResponse(content=hub_challenge, status_code=200)
    else:
        logger.error(f"❌ Webhook verification failed: invalid token or mode")
        raise HTTPException(
            status_code=403,
            detail={"error": "Invalid verification token"}
        )

@app.post("/webhook")
async def handle_webhook(request: Request):
    """
    WhatsApp webhook endpoint for receiving messages
    
    This endpoint receives WhatsApp messages and events from Meta.
    For now, it just logs the payload and returns success.
    """
    try:
        # Get the JSON payload
        payload = await request.json()
        
        # Log the incoming webhook
        logger.info("📨 Received WhatsApp webhook")
        logger.info(f"📋 Headers: {dict(request.headers)}")
        logger.info(f"📄 Payload: {json.dumps(payload, indent=2)}")
        
        # Extract message information if present
        if "entry" in payload:
            for entry in payload["entry"]:
                if "changes" in entry:
                    for change in entry["changes"]:
                        if change.get("field") == "messages":
                            value = change.get("value", {})
                            messages = value.get("messages", [])
                            
                            for message in messages:
                                msg_type = message.get("type")
                                from_number = message.get("from")
                                msg_id = message.get("id")
                                
                                logger.info(f"📱 Message: type={msg_type}, from={from_number}, id={msg_id}")
                                
                                if msg_type == "text":
                                    text_body = message.get("text", {}).get("body", "")
                                    logger.info(f"💬 Text message: '{text_body}'")
                                    
                                    # Get contact name
                                    contacts = value.get("contacts", [])
                                    contact_name = "User"
                                    for contact in contacts:
                                        if contact.get("wa_id") == from_number:
                                            contact_name = contact.get("profile", {}).get("name", "User")
                                            break
                                    
                                    # Save user to session management
                                    await session_manager.save_user(from_number, contact_name)
                                    
                                    # Check if user is in QR generation mode
                                    if await session_manager.is_user_in_state(from_number, 'qr'):
                                        await generate_and_send_qr(from_number, text_body)
                                        await session_manager.clear_user_state(from_number)
                                        return {"status": "ok"}
                                    
                                    # Check if user is in download mode  
                                    if await session_manager.is_user_in_state(from_number, 'download'):
                                        if text_body.lower() in ['back', 'menu', 'cancel']:
                                            await session_manager.clear_user_state(from_number)
                                            await process_text_message(from_number, 'start', contact_name)
                                            return {"status": "ok"}
                                        
                                        # Handle quality selection
                                        quality_map = {
                                            '1080p': '1080p',
                                            '720p': '720p', 
                                            '480p': '480p',
                                            '360p': '360p',
                                            'mp3': 'audio',
                                            'audio': 'audio'
                                        }
                                        
                                        selected_quality = quality_map.get(text_body.lower())
                                        if selected_quality:
                                            # Get stored URL from user state
                                            user_state = await session_manager.get_user_state(from_number)
                                            if user_state and user_state.get('data', {}).get('url'):
                                                url = user_state['data']['url']
                                                await process_quality_download(from_number, url, selected_quality, contact_name)
                                                await session_manager.clear_user_state(from_number)
                                                return {"status": "ok"}
                                        
                                        # Handle URL processing in download mode
                                        if text_body.startswith(('http://', 'https://')):
                                            await process_url_download(from_number, text_body, contact_name)
                                            return {"status": "ok"}
                                    
                                    # Process the message and send response
                                    await process_text_message(from_number, text_body, contact_name)
        
        # Return success response
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {str(e)}")
        # Return success even on error to avoid Meta retries
        return {"status": "error", "message": str(e)}

# Startup event
@app.on_event("startup")
async def startup_event():
    """Application startup"""
    import time
    deployment_id = f"DEPLOY_{int(time.time())}"
    
    logger.info("🚀 Starting Abdi WhatsApp Bot...")
    logger.info(f"📦 Deployment ID: {deployment_id}")
    logger.info(f"⏰ Timestamp: {int(time.time())}")
    logger.info(f"📱 Phone Number ID: {PHONE_NUMBER_ID}")
    logger.info(f"🔑 Verify Token: {VERIFY_TOKEN}")
    logger.info(f"🏢 WABA ID: {WABA_ID}")
    logger.info(f"🔗 Webhook URL: https://your-domain.railway.app/webhook")
    
    # Initialize session manager with proper async setup
    logger.info("🔄 Initializing session manager...")
    await session_manager.initialize()
    
    logger.info("✅ WhatsApp Bot is ready for webhook verification!")

# Shutdown event  
@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown"""
    logger.info("🛞 Shutting down WhatsApp Bot...")
    await cleanup_session()

def main():
    """Main function to run the FastAPI server"""
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"🌐 Starting server on host 0.0.0.0 port {port}")
    
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    main()