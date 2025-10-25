import os
import logging
import instaloader
import yt_dlp
import requests
from flask import Flask, request, jsonify
from config import PHONE_NUMBER_ID, WHATSAPP_TOKEN, VERIFY_TOKEN, INSTAGRAM_COOKIES_FILE

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WhatsAppMessenger:
    """Simple WhatsApp messenger for sending messages"""
    
    def __init__(self, access_token: str, phone_number_id: str):
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.api_url = f"https://graph.facebook.com/v17.0/{phone_number_id}/messages"
    
    def send_message(self, message: str, recipient_id: str):
        """Send a text message via WhatsApp API"""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": recipient_id,
            "text": {
                "body": message
            }
        }
        
        try:
            response = requests.post(self.api_url, json=payload, headers=headers)
            if response.status_code == 200:
                logger.info(f"✅ Message sent to {recipient_id}")
                return True
            else:
                logger.error(f"❌ Failed to send message: {response.text}")
                return False
        except Exception as e:
            logger.error(f"❌ Error sending message: {e}")
            return False

# Initialize WhatsApp messenger
messenger = WhatsAppMessenger(WHATSAPP_TOKEN, PHONE_NUMBER_ID)

def extract_instagram_reel_info(url: str) -> dict:
    """Extract Instagram reel title and creator information using instaloader with cookies"""
    try:
        # Extract shortcode from URL
        # Handle different URL formats
        if '/reel/' in url:
            # Extract shortcode from /reel/shortcode/ or /reel/shortcode
            parts = url.split('/reel/')
            if len(parts) > 1:
                shortcode_part = parts[1].strip('/')
                shortcode = shortcode_part.split('/')[0] if '/' in shortcode_part else shortcode_part
            else:
                raise ValueError("Invalid Instagram reel URL")
        else:
            raise ValueError("Not an Instagram reel URL")
        
        logger.info(f"Extracting info for Instagram reel with shortcode: {shortcode}")
        
        # Create instaloader instance
        L = instaloader.Instaloader()
        
        # Load cookies if file exists
        if os.path.exists(INSTAGRAM_COOKIES_FILE):
            logger.info(f"Loading Instagram cookies from: {INSTAGRAM_COOKIES_FILE}")
            try:
                # Load session from Netscape format cookies
                L.context._session.cookies.clear()
                with open(INSTAGRAM_COOKIES_FILE, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and '\t' in line:
                            parts = line.split('\t')
                            if len(parts) >= 7 and '.instagram.com' in parts[0]:
                                domain = parts[0]
                                name = parts[5]
                                value = parts[6]
                                L.context._session.cookies.set(name, value, domain=domain)
                logger.info("✅ Successfully loaded Instagram cookies")
            except Exception as e:
                logger.error(f"❌ Failed to load cookies: {e}")
        else:
            logger.warning("No Instagram cookies file found")
        
        # Load post using shortcode
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        # Extract title and creator
        title = post.caption[:100] + "..." if post.caption and len(post.caption) > 100 else (post.caption or "Instagram Reel")
        creator = f"@{post.owner_username}" if post.owner_username else "Unknown"
        
        logger.info(f"✅ Extracted title: {title}")
        logger.info(f"✅ Extracted creator: {creator}")
        
        return {
            'title': title,
            'creator': creator,
            'success': True
        }
    except Exception as e:
        logger.error(f"❌ Failed to extract Instagram reel info: {e}")
        return {
            'title': "Instagram Reel",
            'creator': "Unknown",
            'success': False,
            'error': str(e)
        }

def download_instagram_reel(url: str) -> str:
    """Download Instagram reel using instaloader"""
    try:
        import tempfile
        import uuid
        
        # Create temporary directory
        temp_dir = tempfile.mkdtemp()
        logger.info(f"Created temporary directory: {temp_dir}")
        
        # Create instaloader instance
        L = instaloader.Instaloader(
            download_videos=True,
            download_video_thumbnails=False,
            download_comments=False,
            save_metadata=False,
            compress_json=False,
            post_metadata_txt_pattern="",
            quiet=True
        )
        
        # Extract shortcode from URL
        shortcode = url.split("/")[-2]
        logger.info(f"Downloading Instagram reel with shortcode: {shortcode}")
        
        # Load post using shortcode
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        # Download the post
        L.download_post(post, target=shortcode)
        
        # Find downloaded video file
        video_file = None
        for root, dirs, files in os.walk(temp_dir):
            for file in files:
                if file.endswith('.mp4'):
                    video_file = os.path.join(root, file)
                    break
            if video_file:
                break
        
        # If no MP4 found, look for other video formats
        if not video_file:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith(('.mov', '.avi', '.mkv')):
                        video_file = os.path.join(root, file)
                        break
                if video_file:
                    break
        
        if not video_file:
            raise Exception("No video file found after download")
        
        # Move file to downloads directory with a clean name
        downloads_dir = "downloads"
        if not os.path.exists(downloads_dir):
            os.makedirs(downloads_dir)
            
        filename = f"instagram_reel_{shortcode}.mp4"
        final_path = os.path.join(downloads_dir, filename)
        os.rename(video_file, final_path)
        
        logger.info(f"✅ Successfully downloaded to: {final_path}")
        return final_path
    except Exception as e:
        logger.error(f"❌ Failed to download Instagram reel: {e}")
        raise

def process_message(recipient_id: str, text: str):
    """Process incoming message and handle Instagram reel download"""
    logger.info(f"📥 Processing message from {recipient_id}: {text}")
    
    # Check if it's an Instagram reel URL
    if "instagram.com/reel/" in text:
        logger.info(f"🔄 Processing Instagram reel URL from user {recipient_id}: {text}")
        messenger.send_message("🔄 *Processing Instagram Reel link...*", recipient_id)
        
        try:
            # Extract real title and creator information
            messenger.send_message("📥 *Extracting Instagram reel information...*", recipient_id)
            reel_info = extract_instagram_reel_info(text)
            
            if reel_info['success']:
                title = reel_info['title']
                creator = reel_info['creator']
                
                # Send info message with real title and creator
                info_message = f"📹 *{title}*\n👤 *Creator: {creator}*"
                messenger.send_message(info_message, recipient_id)
                
                # Download the reel
                messenger.send_message("⬇️ *Downloading video file...*", recipient_id)
                file_path = download_instagram_reel(text)
                
                # Check if file was downloaded successfully
                if os.path.exists(file_path):
                    file_size = os.path.getsize(file_path)
                    size_mb = file_size / (1024 * 1024)
                    messenger.send_message(f"✅ *Successfully downloaded!* Size: {size_mb:.1f}MB", recipient_id)
                    messenger.send_message(f"📎 *File saved to:* {file_path}", recipient_id)
                else:
                    messenger.send_message("❌ *Download failed*", recipient_id)
            else:
                messenger.send_message(f"❌ *Failed to extract Instagram reel info*\nError: {reel_info['error']}", recipient_id)
                
        except Exception as e:
            logger.error(f"Instagram reel handling failed: {e}")
            messenger.send_message(f"❌ *Failed to process Instagram reel*\nError: {str(e)}", recipient_id)
    else:
        # Handle other messages
        messenger.send_message("👋 *Hello! Send me an Instagram reel link to download it.*", recipient_id)

def verify_webhook(mode: str, token: str, challenge: str) -> tuple:
    """Verify webhook subscription"""
    if mode and token:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            logger.info("✅ Webhook verified successfully")
            return challenge, 200
        else:
            logger.error("❌ Webhook verification failed")
            return "Verification failed", 403
    return "Verification failed", 403

# Flask app for webhook
app = Flask(__name__)

@app.route('/', methods=['GET'])
def verify():
    """Verify webhook subscription"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    response, status = verify_webhook(mode, token, challenge)
    if status == 200:
        return challenge, 200
    else:
        return response, status

@app.route('/', methods=['POST'])
def webhook():
    """Handle incoming webhook events"""
    data = request.get_json()
    
    try:
        if data and data.get('entry'):
            for entry in data['entry']:
                if entry.get('changes'):
                    for change in entry['changes']:
                        value = change.get('value', {})
                        
                        # Handle messages
                        if value.get('messages'):
                            for message in value['messages']:
                                # Get sender information
                                recipient_id = message.get('from')
                                message_type = message.get('type')
                                
                                if message_type == 'text':
                                    text = message['text'].get('body', '')
                                    logger.info(f"Received message from {recipient_id}: {text}")
                                    # Process the message
                                    process_message(recipient_id, text)
                                else:
                                    # Handle other message types (media, etc.)
                                    logger.info(f"Received {message_type} message from {recipient_id}")
                                    # For now, send a generic response for non-text messages
                                    process_message(recipient_id, "Please send a text message or a link to download content.")
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🚀 Starting WhatsApp Bot Webhook Server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)