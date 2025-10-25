import requests
from bs4 import BeautifulSoup
import re

def extract_instagram_info(url):
    """Extract Instagram reel information using web scraping"""
    try:
        # Set headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        # Make request to Instagram URL
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Parse HTML content
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title from meta tags
        title = "Instagram Reel"
        og_title = soup.find('meta', property='og:title')
        if og_title and og_title.get('content'):
            title = og_title['content']
        
        # Extract creator/username
        creator = "Unknown"
        
        # Try to extract from URL
        if 'instagram.com' in url:
            # Extract username from URL pattern
            match = re.search(r'instagram\.com/([^/]+)/', url)
            if match:
                creator = f"@{match.group(1)}"
        
        # Try to find from meta tags
        og_description = soup.find('meta', property='og:description')
        if og_description and og_description.get('content'):
            desc = og_description['content']
            # Try to extract username from description
            username_match = re.search(r'(@[a-zA-Z0-9._]+)', desc)
            if username_match:
                creator = username_match.group(1)
        
        # Try to find username from other meta tags
        profile_meta = soup.find('meta', property='og:site_name')
        if profile_meta and profile_meta.get('content') and profile_meta['content'] != 'Instagram':
            creator = profile_meta['content']
        
        return {
            'title': title,
            'creator': creator
        }
    except Exception as e:
        print(f"Failed to extract Instagram info: {e}")
        return {
            'title': "Instagram Reel",
            'creator': "Unknown"
        }

# Test with the provided URL
url = "https://www.instagram.com/reel/DL452nITuB3"
info = extract_instagram_info(url)
print(f"Title: {info['title']}")
print(f"Creator: {info['creator']}")