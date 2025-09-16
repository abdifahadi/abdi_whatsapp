import asyncio
import aiofiles
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import (
    YOUTUBE_API_KEY, 
    YOUTUBE_CHANNEL_ID, 
    YOUTUBE_CHECK_INTERVAL,
    DATA_DIR
)

logger = logging.getLogger(__name__)

class YouTubeMonitor:
    def __init__(self, whatsapp_sender):
        """
        Initialize YouTube Monitor for WhatsApp
        
        Args:
            whatsapp_sender: WhatsApp sender instance for sending notifications
        """
        self.whatsapp_sender = whatsapp_sender
        self.youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        self.data_file = Path(DATA_DIR) / 'last_video.json'
        self.user_chats_file = Path(DATA_DIR) / 'whatsapp_users.json'
        
        # Ensure data directory exists
        Path(DATA_DIR).mkdir(exist_ok=True)
        
        # Professional notification templates
        self.notification_templates = [
            "🔥 *New Video Just Dropped! Don't Miss This!*",
            "🎬 *Fresh Content Alert! Watch Now!*",
            "✨ *Latest Upload Available! Check It Out!*",
            "🚀 *New Video Released! Must Watch!*",
            "📺 *Breaking: New Content Just Published!*"
        ]
    
    async def save_last_video_id(self, video_id: str, video_title: str) -> None:
        """Save the last processed video ID to prevent duplicates"""
        try:
            data = {
                'video_id': video_id,
                'video_title': video_title,
                'timestamp': datetime.now().isoformat(),
                'notified_at': datetime.now().isoformat()
            }
            
            async with aiofiles.open(self.data_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))
                
            logger.info(f"Saved last video ID: {video_id}")
            
        except Exception as e:
            logger.error(f"Error saving last video ID: {e}")
    
    async def load_last_video_id(self) -> Optional[str]:
        """Load the last processed video ID"""
        try:
            if not self.data_file.exists():
                return None
                
            async with aiofiles.open(self.data_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                data = json.loads(content)
                return data.get('video_id')
                
        except Exception as e:
            logger.error(f"Error loading last video ID: {e}")
            return None
    
    async def save_user_chat(self, phone_number: str) -> None:
        """Save user phone number for notifications"""
        try:
            phone_numbers = await self.load_user_chats()
            if phone_number not in phone_numbers:
                phone_numbers.append(phone_number)
                
                async with aiofiles.open(self.user_chats_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(phone_numbers, indent=2))
                    
                logger.info(f"Saved new user phone number: {phone_number}")
                
        except Exception as e:
            logger.error(f"Error saving user phone number: {e}")
    
    async def load_user_chats(self) -> List[str]:
        """Load all user phone numbers"""
        try:
            if not self.user_chats_file.exists():
                return []
                
            async with aiofiles.open(self.user_chats_file, 'r', encoding='utf-8') as f:
                content = await f.read()
                return json.loads(content)
                
        except Exception as e:
            logger.error(f"Error loading user chats: {e}")
            return []
    
    async def get_latest_video(self) -> Optional[Dict[str, Any]]:
        """Get the latest video from the monitored channel"""
        try:
            # Get channel uploads playlist
            channel_response = self.youtube.channels().list(
                part='contentDetails',
                id=YOUTUBE_CHANNEL_ID
            ).execute()
            
            if not channel_response['items']:
                logger.warning(f"Channel {YOUTUBE_CHANNEL_ID} not found")
                return None
            
            uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            
            # Get latest video from uploads playlist
            playlist_response = self.youtube.playlistItems().list(
                part='snippet',
                playlistId=uploads_playlist_id,
                maxResults=1
            ).execute()
            
            if not playlist_response['items']:
                logger.info("No videos found in channel")
                return None
            
            video_data = playlist_response['items'][0]['snippet']
            
            return {
                'video_id': video_data['resourceId']['videoId'],
                'title': video_data['title'],
                'description': video_data['description'],
                'published_at': video_data['publishedAt'],
                'thumbnail': video_data['thumbnails'].get('high', {}).get('url', ''),
                'channel_title': video_data['channelTitle']
            }
            
        except HttpError as e:
            logger.error(f"YouTube API error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error getting latest video: {e}")
            return None
    
    async def send_notification(self, video_info: Dict[str, Any]) -> None:
        """Send video notification to WhatsApp users"""
        try:
            # Create video URL
            video_url = f"https://www.youtube.com/watch?v={video_info['video_id']}"
            
            # Select random notification template
            import random
            title_template = random.choice(self.notification_templates)
            
            # Create notification message
            message = f"{title_template}\n\n"
            message += f"📺 *{video_info['title']}*\n\n"
            message += f"🔗 {video_url}\n\n"
            message += f"📅 Published: {self._format_date(video_info['published_at'])}"
            
            # Get phone numbers
            phone_numbers = await self.load_user_chats()
            
            if not phone_numbers:
                logger.warning("No phone numbers found for notification")
                return
            
            # Send notifications via WhatsApp
            sent_count = await self.whatsapp_sender.send_notification_to_users(phone_numbers, message)
            
            logger.info(f"Video notification sent to {sent_count} WhatsApp users")
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
    
    def _format_date(self, iso_date: str) -> str:
        """Format ISO date string to readable format"""
        try:
            dt = datetime.fromisoformat(iso_date.replace('Z', '+00:00'))
            return dt.strftime('%B %d, %Y at %I:%M %p UTC')
        except Exception:
            return iso_date
    
    async def check_for_new_video(self) -> None:
        """Check for new videos and send notifications"""
        try:
            logger.info("Checking for new videos...")
            
            # Get latest video
            latest_video = await self.get_latest_video()
            if not latest_video:
                logger.info("No latest video found")
                return
            
            # Check if this video was already notified
            last_video_id = await self.load_last_video_id()
            current_video_id = latest_video['video_id']
            
            if last_video_id == current_video_id:
                logger.info(f"Video {current_video_id} already notified")
                return
            
            # New video found! Send notification
            logger.info(f"New video found: {latest_video['title']} ({current_video_id})")
            await self.send_notification(latest_video)
            
            # Save this video ID as the last notified
            await self.save_last_video_id(current_video_id, latest_video['title'])
            
        except Exception as e:
            logger.error(f"Error checking for new video: {e}")
    
    async def start_monitoring(self) -> None:
        """Start the monitoring loop"""
        logger.info(f"Starting YouTube channel monitoring for channel: {YOUTUBE_CHANNEL_ID}")
        logger.info(f"Check interval: {YOUTUBE_CHECK_INTERVAL} seconds")
        logger.info("📱 Notifications will be sent via WhatsApp")
        
        while True:
            try:
                await self.check_for_new_video()
                await asyncio.sleep(YOUTUBE_CHECK_INTERVAL)
                
            except asyncio.CancelledError:
                logger.info("YouTube monitoring cancelled")
                break
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                # Wait a bit before retrying to avoid spam
                await asyncio.sleep(60)