import instaloader
import os

def test_instagram_with_cookies():
    """Test Instagram access with cookies"""
    # Create instaloader instance
    L = instaloader.Instaloader()
    
    # Try to load cookies if file exists
    cookies_file = "cookies.txt"
    if os.path.exists(cookies_file):
        print(f"Found cookies file: {cookies_file}")
        try:
            # Load session from Netscape format cookies
            L.context._session.cookies.clear()
            with open(cookies_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '\t' in line:
                        parts = line.split('\t')
                        if len(parts) >= 7 and '.instagram.com' in parts[0]:
                            domain = parts[0]
                            name = parts[5]
                            value = parts[6]
                            L.context._session.cookies.set(name, value, domain=domain)
            print("✅ Successfully loaded cookies")
        except Exception as e:
            print(f"❌ Failed to load cookies: {e}")
    else:
        print("❌ No cookies file found")
    
    # Test with the Instagram reel
    try:
        shortcode = "DL452nITuB3"
        print(f"Testing with shortcode: {shortcode}")
        post = instaloader.Post.from_shortcode(L.context, shortcode)
        title = post.caption[:100] + "..." if post.caption and len(post.caption) > 100 else (post.caption or "Instagram Reel")
        creator = f"@{post.owner_username}" if post.owner_username else "Unknown"
        print(f"✅ Title: {title}")
        print(f"✅ Creator: {creator}")
        return True
    except Exception as e:
        print(f"❌ Failed to access Instagram: {e}")
        return False

if __name__ == "__main__":
    test_instagram_with_cookies()