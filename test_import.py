"""
Test script to verify WhatsApp bot can be imported without errors
"""
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_import(module_name):
    """Test if a module can be imported"""
    try:
        __import__(module_name)
        print(f"✅ {module_name} imported successfully")
        return True
    except ImportError:
        print(f"❌ {module_name} not found - install with: pip install {module_name}")
        return False

try:
    # Try to import the main module
    import whatsapp_bot
    print("✅ WhatsApp bot module imported successfully!")
    
    # Try to import dependencies
    dependencies = [
        "fastapi",
        "uvicorn", 
        "yt_dlp",
        "aiohttp",
        "instaloader",
        "qrcode",
        "PIL"
    ]
    
    print("\nChecking dependencies:")
    missing_deps = []
    for dep in dependencies:
        if not test_import(dep):
            missing_deps.append(dep)
    
    if missing_deps:
        print(f"\n⚠️  Missing dependencies: {', '.join(missing_deps)}")
        print("Please install them with: pip install -r requirements.txt")
    else:
        print("\n✅ All dependencies imported successfully!")
    
    print("\n🎉 WhatsApp bot is ready to run!")
    print("To start the bot, run: python whatsapp_bot.py")
    
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Please make sure all dependencies are installed:")
    print("pip install -r requirements.txt")
    
except Exception as e:
    print(f"❌ Unexpected error: {e}")