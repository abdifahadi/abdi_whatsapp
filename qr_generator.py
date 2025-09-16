# QR Code Generator with Professional Branding and Centering
import os
import time
import qrcode
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
from typing import Optional, Union
import logging

logger = logging.getLogger(__name__)

class QRCodeGenerator:
    """High-quality QR code generator with custom branding"""
    
    def __init__(self, temp_dir: str = "temp"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)
        
        # Font configuration - look in current directory first
        self.font_paths = [
            "ShadowHand.ttf",  # Primary font in current directory
            "Elements.ttf",  # Fallback font
        ]
        self.fixed_text = "@abdifahadi"  # Branding text
        
    def _get_font(self, size: int) -> Union[ImageFont.FreeTypeFont, ImageFont.ImageFont]:
        """Get font with fallback support"""
        for font_path in self.font_paths:
            if os.path.exists(font_path):
                try:
                    return ImageFont.truetype(font_path, size)
                except Exception as e:
                    logger.debug(f"Failed to load font {font_path}: {e}")
                    continue
        
        # Fallback to default font
        logger.warning("⚠️ Custom fonts not found, using default font")
        return ImageFont.load_default()
    
    async def generate_qr(self, data: str, overlay: Optional[str] = None, font_file: Optional[str] = None) -> str:
        """
        Generate QR code with embedded center text
        
        Args:
            data: Text or URL to encode in QR code
            overlay: Custom overlay text (defaults to @abdifahadi)
            font_file: Custom font file to use
            
        Returns:
            Path to generated QR code image
        """
        try:
            # Use custom overlay text if provided
            overlay_text = overlay or self.fixed_text
            
            # Create QR code with high error correction for center text
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.ERROR_CORRECT_H,  # High error correction allows center overlay
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            # Generate base QR image and convert to PIL Image
            qr_img = qr.make_image(fill_color="black", back_color="white")
            # Convert to RGB if it's not already
            if hasattr(qr_img, 'convert'):
                img_qr = qr_img.convert("RGB")
            else:
                # Handle case where make_image returns different format
                img_qr = Image.new("RGB", qr_img.size, "white")
                img_qr.paste(qr_img)
            
            # High resolution upscaling for quality
            upscale = 6
            img_qr = img_qr.resize(
                (img_qr.size[0] * upscale, img_qr.size[1] * upscale), 
                Image.Resampling.NEAREST
            )
            img_w, img_h = img_qr.size
            draw = ImageDraw.Draw(img_qr)
            
            img_w, img_h = img_qr.size
            draw = ImageDraw.Draw(img_qr)
            
            # Font setup with auto-sizing
            base_font_size = int(img_w * 0.12)  # 12% of QR width
            font = self._get_font(base_font_size)
            
            # Calculate text dimensions
            text_bbox = draw.textbbox((0, 0), overlay_text, font=font)
            text_w = text_bbox[2] - text_bbox[0]
            text_h = text_bbox[3] - text_bbox[1]
            
            # Dynamically scale font if text is too wide (max 70% of QR width)
            max_width = img_w * 0.7
            scale_factor = 0.9
            min_font_size = 8
            
            while text_w > max_width and base_font_size > min_font_size:
                base_font_size = max(min_font_size, int(base_font_size * scale_factor))
                font = self._get_font(base_font_size)
                text_bbox = draw.textbbox((0, 0), overlay_text, font=font)
                text_w = text_bbox[2] - text_bbox[0]
                text_h = text_bbox[3] - text_bbox[1]
            
            # Center positioning with optical centering adjustment
            x = (img_w - text_w) // 2
            y = (img_h - text_h) // 2
            
            # Apply small vertical offset for optical centering (text tends to look high)
            optical_offset = int(text_h * 0.02)  # 2% of text height
            y += optical_offset
            
            # Create rounded white background for text readability
            padding = max(int(text_h * 0.15), 8)  # 15% of text height, minimum 8px
            
            # Create rounded rectangle background
            bg_x1 = x - padding
            bg_y1 = y - padding
            bg_x2 = x + text_w + padding
            bg_y2 = y + text_h + padding
            
            # Draw rounded rectangle (simulate with multiple rectangles)
            corner_radius = min(padding // 2, 8)
            
            # Main rectangle
            draw.rectangle([bg_x1 + corner_radius, bg_y1, bg_x2 - corner_radius, bg_y2], fill="white")
            draw.rectangle([bg_x1, bg_y1 + corner_radius, bg_x2, bg_y2 - corner_radius], fill="white")
            
            # Corner circles for rounded effect
            draw.ellipse([bg_x1, bg_y1, bg_x1 + 2*corner_radius, bg_y1 + 2*corner_radius], fill="white")
            draw.ellipse([bg_x2 - 2*corner_radius, bg_y1, bg_x2, bg_y1 + 2*corner_radius], fill="white")
            draw.ellipse([bg_x1, bg_y2 - 2*corner_radius, bg_x1 + 2*corner_radius, bg_y2], fill="white")
            draw.ellipse([bg_x2 - 2*corner_radius, bg_y2 - 2*corner_radius, bg_x2, bg_y2], fill="white")
            
            # Draw the overlay text
            draw.text((x, y), overlay_text, font=font, fill="black")
            
            # Final downscale for smoothness using high-quality resampling
            final_img = img_qr.resize((img_w // upscale, img_h // upscale), Image.Resampling.LANCZOS)
            
            # Generate unique filename with timestamp
            timestamp = int(time.time())
            file_path = self.temp_dir / f"qr_branded_{timestamp}.png"
            
            # Save with optimization
            final_img.save(file_path, "PNG", optimize=True, quality=95)
            
            logger.info(f"✅ QR code generated: {file_path}")
            return str(file_path)
            
        except Exception as e:
            logger.error(f"❌ QR code generation failed: {e}")
            raise
    
    def cleanup_old_qr_files(self, max_age_minutes: int = 30):
        """Clean up old QR code files"""
        try:
            current_time = time.time()
            removed_count = 0
            
            for file_path in self.temp_dir.glob("qr_*.png"):
                try:
                    file_age = current_time - file_path.stat().st_mtime
                    if file_age > (max_age_minutes * 60):
                        file_path.unlink()
                        removed_count += 1
                except Exception as e:
                    logger.debug(f"Error removing old QR file {file_path}: {e}")
            
            if removed_count > 0:
                logger.info(f"🧹 Cleaned up {removed_count} old QR code files")
                
        except Exception as e:
            logger.error(f"❌ QR cleanup failed: {e}")

# Global QR generator instance
qr_generator = QRCodeGenerator()