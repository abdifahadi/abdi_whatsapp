import asyncio
import aiohttp
import requests
import os
import mimetypes
import logging
from typing import Dict, List, Optional

from config import WHATSAPP_TOKEN, WHATSAPP_MESSAGES_URL, WHATSAPP_MEDIA_URL, PHONE_NUMBER_ID

logger = logging.getLogger(__name__)

class WhatsAppSender:
    """Handles sending messages and media via WhatsApp Cloud API"""
    
    def __init__(self):
        self.token = WHATSAPP_TOKEN
        self.messages_url = WHATSAPP_MESSAGES_URL
        self.media_url = WHATSAPP_MEDIA_URL
        self.phone_number_id = PHONE_NUMBER_ID
    
    def get_headers(self) -> Dict[str, str]:
        """Get headers for WhatsApp API requests"""
        return {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
    
    async def send_message(self, phone_number: str, message: str) -> bool:
        """Send text message via WhatsApp"""
        try:
            headers = self.get_headers()
            
            data = {
                'messaging_product': 'whatsapp',
                'to': phone_number,
                'type': 'text',
                'text': {
                    'body': message
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.messages_url, headers=headers, json=data) as response:
                    if response.status == 200:
                        logger.info(f"✅ Message sent to {phone_number}")
                        return True
                    else:
                        response_text = await response.text()
                        logger.error(f"❌ Failed to send message: {response.status} - {response_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"❌ WhatsApp message error: {e}")
            return False
    
    async def send_interactive_buttons(self, phone_number: str, body_text: str, buttons: List[Dict]) -> bool:
        """Send interactive message with buttons"""
        try:
            headers = self.get_headers()
            
            # Convert buttons to WhatsApp format (max 3 buttons)
            button_components = []
            for i, button in enumerate(buttons[:3]):
                button_components.append({
                    "type": "reply",
                    "reply": {
                        "id": button["id"],
                        "title": button["title"]
                    }
                })
            
            data = {
                'messaging_product': 'whatsapp',
                'to': phone_number,
                'type': 'interactive',
                'interactive': {
                    'type': 'button',
                    'body': {
                        'text': body_text
                    },
                    'action': {
                        'buttons': button_components
                    }
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.messages_url, headers=headers, json=data) as response:
                    if response.status == 200:
                        logger.info(f"✅ Interactive message sent to {phone_number}")
                        return True
                    else:
                        response_text = await response.text()
                        logger.error(f"❌ Failed to send interactive message: {response.status} - {response_text}")
                        # Fallback to regular text message
                        return await self.send_message(phone_number, body_text)
                        
        except Exception as e:
            logger.error(f"❌ WhatsApp interactive message error: {e}")
            # Fallback to regular text message
            return await self.send_message(phone_number, body_text)
    
    async def send_interactive_list(self, phone_number: str, body_text: str, button_text: str, sections: List[Dict]) -> bool:
        """Send interactive message with list"""
        try:
            headers = self.get_headers()
            
            data = {
                'messaging_product': 'whatsapp',
                'to': phone_number,
                'type': 'interactive',
                'interactive': {
                    'type': 'list',
                    'body': {
                        'text': body_text
                    },
                    'action': {
                        'button': button_text,
                        'sections': sections
                    }
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.messages_url, headers=headers, json=data) as response:
                    if response.status == 200:
                        logger.info(f"✅ Interactive list sent to {phone_number}")
                        return True
                    else:
                        response_text = await response.text()
                        logger.error(f"❌ Failed to send interactive list: {response.status} - {response_text}")
                        # Fallback to regular text message
                        return await self.send_message(phone_number, body_text)
                        
        except Exception as e:
            logger.error(f"❌ WhatsApp interactive list error: {e}")
            # Fallback to regular text message
            return await self.send_message(phone_number, body_text)
    
    def upload_media(self, file_path: str) -> Optional[str]:
        """Upload media to WhatsApp and get media ID"""
        try:
            headers = {
                'Authorization': f'Bearer {self.token}'
            }
            
            # Detect MIME type
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                if file_path.lower().endswith(('.mp4', '.mov', '.avi')):
                    mime_type = 'video/mp4'
                elif file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    mime_type = 'image/jpeg'
                elif file_path.lower().endswith('.mp3'):
                    mime_type = 'audio/mpeg'
                else:
                    mime_type = 'application/octet-stream'
            
            data = {
                'messaging_product': 'whatsapp',
                'type': mime_type
            }
            
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f, mime_type)}
                
                response = requests.post(
                    self.media_url,
                    headers=headers,
                    data=data,
                    files=files,
                    timeout=60
                )
                
                if response.status_code == 200:
                    result = response.json()
                    media_id = result.get('id')
                    logger.info(f"✅ Media uploaded: {media_id}")
                    return media_id
                else:
                    logger.error(f"❌ Media upload failed: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"❌ Media upload error: {e}")
            return None
    
    async def send_media_by_id(self, phone_number: str, media_id: str, media_type: str, caption: str = "") -> bool:
        """Send media using media ID"""
        try:
            headers = self.get_headers()
            
            media_data = {
                'id': media_id
            }
            
            if caption:
                media_data['caption'] = caption
            
            data = {
                'messaging_product': 'whatsapp',
                'to': phone_number,
                'type': media_type,
                media_type: media_data
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.messages_url, headers=headers, json=data) as response:
                    if response.status == 200:
                        logger.info(f"✅ Media sent by ID to {phone_number}")
                        return True
                    else:
                        response_text = await response.text()
                        logger.error(f"❌ Failed to send media by ID: {response.status} - {response_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"❌ WhatsApp media by ID error: {e}")
            return False
    
    async def send_media_by_url(self, phone_number: str, media_url: str, media_type: str, caption: str = "") -> bool:
        """Send media using URL"""
        try:
            headers = self.get_headers()
            
            media_data = {
                'link': media_url
            }
            
            if caption:
                media_data['caption'] = caption
            
            data = {
                'messaging_product': 'whatsapp',
                'to': phone_number,
                'type': media_type,
                media_type: media_data
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.messages_url, headers=headers, json=data) as response:
                    if response.status == 200:
                        logger.info(f"✅ Media sent by URL to {phone_number}")
                        return True
                    else:
                        response_text = await response.text()
                        logger.error(f"❌ Failed to send media by URL: {response.status} - {response_text}")
                        return False
                        
        except Exception as e:
            logger.error(f"❌ WhatsApp media by URL error: {e}")
            return False
    
    async def send_media_file(self, phone_number: str, file_path: str, caption: str = "", media_type: str = 'auto') -> bool:
        """Send media file (upload then send)"""
        try:
            # Auto-detect media type if needed
            if media_type == 'auto':
                if file_path.lower().endswith(('.mp4', '.mov', '.avi')):
                    media_type = 'video'
                elif file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
                    media_type = 'image'
                elif file_path.lower().endswith('.mp3'):
                    media_type = 'audio'
                else:
                    media_type = 'document'
            
            # Upload media first
            media_id = self.upload_media(file_path)
            
            if media_id:
                # Send using media ID
                return await self.send_media_by_id(phone_number, media_id, media_type, caption)
            else:
                logger.error("❌ Failed to upload media for sending")
                return False
                
        except Exception as e:
            logger.error(f"❌ Send media file error: {e}")
            return False
    
    def get_whatsapp_media_type(self, file_path: str) -> str:
        """Get WhatsApp media type from file path"""
        if file_path.lower().endswith(('.mp4', '.mov', '.avi')):
            return 'video'
        elif file_path.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp')):
            return 'image'
        elif file_path.lower().endswith('.mp3'):
            return 'audio'
        else:
            return 'document'
    
    async def send_notification_to_users(self, user_list: List[str], message: str) -> int:
        """Send notification to multiple users (for YouTube notifications)"""
        sent_count = 0
        
        for phone_number in user_list:
            try:
                success = await self.send_message(phone_number, message)
                if success:
                    sent_count += 1
                # Small delay to avoid rate limits
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"❌ Failed to send notification to {phone_number}: {e}")
        
        logger.info(f"📡 Sent notifications to {sent_count}/{len(user_list)} users")
        return sent_count