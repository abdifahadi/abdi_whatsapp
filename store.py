# Session and State Management Module
import json
import os
import asyncio
from pathlib import Path
from typing import Dict, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    """Lightweight session and state management using JSON files"""
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # File paths
        self.users_file = self.data_dir / "users.json"
        self.state_file = self.data_dir / "state.json"
        self.last_video_file = self.data_dir / "last_video_id_whatsapp.txt"
        
        # In-memory cache
        self._users = {}
        self._states = {}
        self._lock: Optional[asyncio.Lock] = None  # Will be initialized in initialize() method
        self._initialized = False
    
    async def initialize(self):
        """Initialize the session manager with async setup"""
        if self._initialized:
            return
            
        # Create async lock
        self._lock = asyncio.Lock()
        
        # Load data
        await self._load_data()
        self._initialized = True
        logger.info("✅ SessionManager initialized")
    
    async def _ensure_initialized(self):
        """Ensure the session manager is initialized"""
        if not self._initialized:
            await self.initialize()
    
    async def _load_data(self):
        """Load data from JSON files"""
        if self._lock is None:
            return  # Not initialized yet
            
        async with self._lock:
            try:
                # Load users
                if self.users_file.exists():
                    with open(self.users_file, 'r', encoding='utf-8') as f:
                        self._users = json.load(f)
                        logger.info(f"✅ Loaded {len(self._users)} users from {self.users_file}")
                
                # Load states
                if self.state_file.exists():
                    with open(self.state_file, 'r', encoding='utf-8') as f:
                        self._states = json.load(f)
                        logger.info(f"✅ Loaded {len(self._states)} user states from {self.state_file}")
                        
            except Exception as e:
                logger.error(f"❌ Failed to load session data: {e}")
                self._users = {}
                self._states = {}
    
    async def _save_users(self):
        """Save users to JSON file"""
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self._users, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ Failed to save users: {e}")
    
    async def _save_states(self):
        """Save states to JSON file"""
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self._states, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"❌ Failed to save states: {e}")
    
    async def save_user(self, phone_number: str, contact_name: str = ""):
        """Save or update user information"""
        await self._ensure_initialized()
        
        async with self._lock:
            user_data = {
                "phone_number": phone_number,
                "contact_name": contact_name,
                "first_seen": self._users.get(phone_number, {}).get("first_seen", datetime.now().isoformat()),
                "last_seen": datetime.now().isoformat(),
                "message_count": self._users.get(phone_number, {}).get("message_count", 0) + 1
            }
            
            self._users[phone_number] = user_data
            await self._save_users()
            logger.debug(f"👤 User saved: {contact_name} ({phone_number})")
    
    async def get_user(self, phone_number: str) -> Optional[Dict]:
        """Get user information"""
        await self._ensure_initialized()
        return self._users.get(phone_number)
    
    async def get_all_users(self) -> Dict[str, Dict]:
        """Get all users for YouTube notifications"""
        await self._ensure_initialized()
        return self._users.copy()
    
    async def set_user_state(self, phone_number: str, state: str, data: Optional[Dict] = None):
        """Set user state (idle, download, qr)"""
        await self._ensure_initialized()
        
        async with self._lock:
            state_data = {
                "state": state,
                "data": data or {},
                "timestamp": datetime.now().isoformat()
            }
            
            self._states[phone_number] = state_data
            await self._save_states()
            logger.debug(f"🔄 User state set: {phone_number} -> {state}")
    
    async def get_user_state(self, phone_number: str) -> Optional[Dict]:
        """Get user state"""
        await self._ensure_initialized()
        return self._states.get(phone_number)
    
    async def clear_user_state(self, phone_number: str):
        """Clear user state (back to idle)"""
        await self._ensure_initialized()
        
        async with self._lock:
            if phone_number in self._states:
                del self._states[phone_number]
                await self._save_states()
                logger.debug(f"🗑️ User state cleared: {phone_number}")
    
    async def is_user_in_state(self, phone_number: str, state: str) -> bool:
        """Check if user is in specific state"""
        user_state = await self.get_user_state(phone_number)
        return bool(user_state and user_state.get("state") == state)
    
    async def save_last_video_id(self, video_id: str):
        """Save last processed YouTube video ID"""
        try:
            with open(self.last_video_file, 'w') as f:
                f.write(video_id)
            logger.debug(f"📹 Last video ID saved: {video_id}")
        except Exception as e:
            logger.error(f"❌ Failed to save last video ID: {e}")
    
    async def get_last_video_id(self) -> Optional[str]:
        """Get last processed YouTube video ID"""
        try:
            if self.last_video_file.exists():
                with open(self.last_video_file, 'r') as f:
                    return f.read().strip()
        except Exception as e:
            logger.error(f"❌ Failed to read last video ID: {e}")
        return None
    
    async def cleanup_old_states(self, max_age_hours: int = 24):
        """Clean up old user states"""
        await self._ensure_initialized()
        
        async with self._lock:
            now = datetime.now()
            to_remove = []
            
            for phone_number, state_data in self._states.items():
                try:
                    timestamp = datetime.fromisoformat(state_data["timestamp"])
                    age_hours = (now - timestamp).total_seconds() / 3600
                    
                    if age_hours > max_age_hours:
                        to_remove.append(phone_number)
                except Exception as e:
                    logger.debug(f"Invalid timestamp for {phone_number}: {e}")
                    to_remove.append(phone_number)
            
            for phone_number in to_remove:
                del self._states[phone_number]
            
            if to_remove:
                await self._save_states()
                logger.info(f"🧹 Cleaned up {len(to_remove)} old user states")

# Global session manager instance
session_manager = SessionManager()