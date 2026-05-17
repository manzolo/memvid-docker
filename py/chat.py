#!/usr/bin/env python3
from flask import Flask, render_template, request, jsonify, send_from_directory
from memvid import MemvidChat
import os
import requests
import logging
import json
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

app = Flask(__name__)

# Global variables
chat = None
ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
model_name = os.getenv("OLLAMA_MODEL", "llama3")

def initialize_chat():
    """Initialize MemvidChat with video and index files"""
    global chat
    video_path = "/app/output/knowledge.mp4"
    index_path = "/app/output/knowledge_index.json"
    
    try:
        if os.path.exists(video_path) and os.path.exists(index_path):
            chat = MemvidChat(video_path, index_path)
            logging.info("✅ MemvidChat initialized successfully")
            return True
        else:
            logging.error("❌ Video or index file not found")
            return False
    except Exception as e:
        logging.error(f"❌ Error initializing chat: {e}")
        return False

def check_ollama_connection():
    """Check if Ollama is accessible"""
    try:
        response = requests.get(f"{ollama_host}/api/tags", timeout=5)
        return response.status_code == 200
    except:
        return False

@app.route('/')
def index():
    """Serve the main chat interface"""
    return render_template('chat.html')

@app.route('/api/chat', methods=['POST'])
def chat_endpoint():
    """Handle chat messages"""
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        
        if not question:
            return jsonify({'error': 'Empty question'}), 400
        
        if not chat:
            return jsonify({'error': 'Chat not initialized. Run process_docs.py first.'}), 500
        
        # Get context from Memvid
        logging.info(f"🤔 Question: {question}")
        memvid_response = chat.chat(question)
        logging.info(f"📚 Memvid Context: {memvid_response}")
        
        # Check Ollama connection
        if not check_ollama_connection():
            return jsonify({
                'context': memvid_response,
                'response': f"⚠️ Ollama not available. Context from documents: {memvid_response}",
                'ollama_available': False
            })
        
        # Send to Ollama
        payload = {
            "model": model_name,
            "prompt": f"Document context: {memvid_response}\nQuestion: {question}\nRespond concisely and precisely, based on the provided context.",
            "stream": False
        }
        
        ollama_response = requests.post(f"{ollama_host}/api/generate", json=payload, timeout=30)
        
        if ollama_response.status_code == 200:
            bot_response = ollama_response.json().get("response", "No response")
            logging.info(f"🤖 Answer: {bot_response}")
            
            return jsonify({
                'context': memvid_response,
                'response': bot_response,
                'ollama_available': True
            })
        else:
            logging.error(f"❌ Ollama Error: {ollama_response.text}")
            return jsonify({
                'context': memvid_response,
                'response': f"❌ Ollama error: {ollama_response.text}",
                'ollama_available': False
            }), 500
            
    except Exception as e:
        logging.error(f"❌ Chat error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status')
def status_endpoint():
    """Get system status"""
    return jsonify({
        'memvid_ready': chat is not None,
        'ollama_available': check_ollama_connection(),
        'model_name': model_name,
        'timestamp': datetime.now().isoformat()
    })

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

if __name__ == '__main__':
    # Initialize chat on startup
    if not initialize_chat():
        logging.warning("⚠️ Chat initialization failed. Make sure to run process_docs.py first.")
    
    # Run Flask app
    app.run(host='0.0.0.0', port=7860, debug=False)