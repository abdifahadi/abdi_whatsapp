import os
from flask import Flask, request, jsonify
import logging
from whatsapp_bot_simple import process_message, verify_webhook

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

@app.route('/', methods=['GET'])
@app.route('/webhook', methods=['GET'])
def verify():
    """Verify webhook subscription"""
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    
    return verify_webhook(mode, token, challenge)

@app.route('/', methods=['POST'])
@app.route('/webhook', methods=['POST'])
def webhook():
    """Handle incoming webhook events"""
    data = request.get_json()
    
    try:
        if data and data.get('entry'):
            for entry in data['entry']:
                if entry.get('changes'):
                    for change in entry['changes']:
                        value = change.get('value', {})
                        
                        # Handle messages
                        if value.get('messages'):
                            for message in value['messages']:
                                # Get sender information
                                recipient_id = message.get('from')
                                message_type = message.get('type')
                                
                                if message_type == 'text':
                                    text = message['text'].get('body', '')
                                    logger.info(f"Received message from {recipient_id}: {text}")
                                    # Process the message
                                    process_message(recipient_id, text)
                                else:
                                    # Handle other message types (media, etc.)
                                    logger.info(f"Received {message_type} message from {recipient_id}")
                                    # For now, send a generic response for non-text messages
                                    process_message(recipient_id, "Please send a text message or a link to download content.")
        
        return jsonify({'status': 'ok'}), 200
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'healthy'}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    logger.info(f"🚀 Starting WhatsApp Bot Webhook Server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)