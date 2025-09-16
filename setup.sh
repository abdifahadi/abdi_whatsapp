#!/bin/bash
# WhatsApp Bot Setup Script

echo "🚀 Setting up Abdi WhatsApp Bot..."

# Create necessary directories
mkdir -p downloads temp data

# Copy environment template
if [ ! -f .env ]; then
    cp .env.example .env
    echo "📝 Created .env file from template"
    echo "⚠️  Please edit .env with your WhatsApp API credentials"
fi

# Copy cookies from parent directory if available
if [ -f ../cookies.txt ] && [ ! -f cookies.txt ]; then
    cp ../cookies.txt .
    echo "📄 Copied Instagram cookies"
fi

if [ -f ../ytcookies.txt ] && [ ! -f ytcookies.txt ]; then
    cp ../ytcookies.txt .
    echo "📄 Copied YouTube cookies"
fi

# Install dependencies
echo "📦 Installing dependencies..."
pip install -r requirements.txt

echo "✅ Setup complete!"
echo ""
echo "🔧 Next steps:"
echo "1. Edit .env with your WhatsApp API credentials"
echo "2. Run: uvicorn app:app --host 0.0.0.0 --port 8080"
echo "3. Set webhook URL: https://your-domain.railway.app/webhook"
echo "4. Use verify token: abdifahadi-whatsapp"
echo ""
echo "📱 Webhook endpoints:"
echo "   GET  /webhook - Verification"
echo "   POST /webhook - Message handling"
echo "   GET  /health  - Health check"