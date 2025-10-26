#!/usr/bin/env python3
"""
Script to check if cookies files are properly configured
"""
import os
import sys

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_cookies_file(file_path, platform_name):
    """Check if cookies file exists and has content"""
    print(f"\n🔍 Checking {platform_name} cookies file: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"❌ {platform_name} cookies file not found!")
        print(f"   Please create {file_path} with your {platform_name} session cookies in Netscape format.")
        return False
    
    # Check file size
    file_size = os.path.getsize(file_path)
    if file_size == 0:
        print(f"❌ {platform_name} cookies file is empty!")
        print(f"   Please add your {platform_name} session cookies to {file_path} in Netscape format.")
        return False
    
    # Check file content
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            lines = content.strip().split('\n')
            
            # Count non-empty lines and cookie lines
            non_empty_lines = [line for line in lines if line.strip() and not line.startswith('#')]
            all_lines = [line for line in lines if line.strip()]
            
            if len(non_empty_lines) == 0:
                print(f"❌ {platform_name} cookies file has no valid cookie entries!")
                print(f"   Please add your {platform_name} session cookies to {file_path} in Netscape format.")
                return False
            
            print(f"✅ {platform_name} cookies file found with {len(all_lines)} total lines ({len(non_empty_lines)} cookie entries)")
            
            # Look for important cookies
            if platform_name == "Instagram":
                important_cookies = ['sessionid', 'ds_user_id', 'csrftoken']
                found_cookies = []
                for line in all_lines:
                    # Handle HttpOnly prefix
                    if line.startswith('#HttpOnly_'):
                        line = line[10:]  # Remove '#HttpOnly_' prefix
                    
                    parts = line.split('\t')
                    if len(parts) >= 7:
                        cookie_name = parts[5]
                        if cookie_name in important_cookies:
                            found_cookies.append(cookie_name)
                
                if 'sessionid' not in found_cookies:
                    print(f"⚠️  Warning: sessionid cookie not found in {file_path}")
                    print(f"   Instagram downloads may fail without a valid sessionid")
                else:
                    print(f"✅ Found important Instagram cookies: {', '.join(found_cookies)}")
                    if 'sessionid' in found_cookies:
                        print("   🔐 sessionid is properly configured for Instagram authentication")
            
            return True
            
    except Exception as e:
        print(f"❌ Error reading {platform_name} cookies file: {str(e)}")
        return False

def main():
    """Main function"""
    print("🍪 Checking cookies configuration for WhatsApp Bot")
    print("=" * 50)
    
    # Check Instagram cookies
    instagram_cookies_path = "cookies.txt"
    instagram_ok = check_cookies_file(instagram_cookies_path, "Instagram")
    
    # Check YouTube cookies
    youtube_cookies_path = "ytcookies.txt"
    youtube_ok = check_cookies_file(youtube_cookies_path, "YouTube")
    
    print("\n" + "=" * 50)
    print("📋 SUMMARY")
    print("=" * 50)
    
    if instagram_ok and youtube_ok:
        print("✅ All cookies files are properly configured!")
        print("🎉 The WhatsApp bot should work correctly with Instagram and YouTube downloads.")
    else:
        print("⚠️  Some cookies files need attention.")
        print("💡 Make sure to add your session cookies in Netscape format to the files.")
        
        if not instagram_ok:
            print("\nFor Instagram cookies:")
            print("1. Log into Instagram in your browser")
            print("2. Use a browser extension like 'Cookie-Editor' to export cookies")
            print("3. Save them in Netscape format to cookies.txt")
            print("4. Make sure to include sessionid and ds_user_id cookies")
            
        if not youtube_ok:
            print("\nFor YouTube cookies:")
            print("1. Log into YouTube/Google in your browser")
            print("2. Use a browser extension like 'Cookie-Editor' to export cookies")
            print("3. Save them in Netscape format to ytcookies.txt")

if __name__ == "__main__":
    main()