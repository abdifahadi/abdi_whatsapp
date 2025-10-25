import instaloader
import re

def extract_instagram_info_with_instaloader(url):
    """Extract Instagram reel title and creator using instaloader"""
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
        
        print(f"Shortcode: {shortcode}")
        
        # Create instaloader instance
        L = instaloader.Instaloader()
        
        # Load post using shortcode
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        
        # Extract title and creator
        title = post.caption[:100] + "..." if post.caption and len(post.caption) > 100 else (post.caption or "Instagram Reel")
        creator = f"@{post.owner_username}" if post.owner_username else "Unknown"
        
        return {
            'title': title,
            'creator': creator
        }
    except Exception as e:
        print(f"Error: {e}")
        return {
            'title': "Instagram Reel",
            'creator': "Unknown"
        }

# Test with the provided URL
url = "https://www.instagram.com/reel/DL452nITuB3"
print("Extracting Instagram reel information...")
info = extract_instagram_info_with_instaloader(url)
print(f"Title: {info['title']}")
print(f"Creator: {info['creator']}")