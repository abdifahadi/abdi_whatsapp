import os
import sys
import time

# Add the current directory to the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from whatsapp_bot import process_message

def test_instagram_reel_download():
    """Test the Instagram reel download functionality"""
    print("🧪 Testing Instagram reel download functionality...")
    
    # Test with the provided Instagram reel URL
    test_url = "https://www.instagram.com/reel/DL452nITuB3"
    print(f"Testing URL: {test_url}")
    
    # Process the message as if it came from WhatsApp
    process_message("test_user", test_url)
    
    # Wait a bit to see the output
    time.sleep(5)
    
    print("\n✅ Test completed. Check the output above to see if:")
    print("1. The title was extracted correctly")
    print("2. The creator was extracted correctly") 
    print("3. The download process started")
    print("4. The file was downloaded to the downloads directory")

if __name__ == "__main__":
    test_instagram_reel_download()