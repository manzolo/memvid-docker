#!/usr/bin/env python3
from memvid import MemvidEncoder, MemvidChat
import os
import sys
import logging
import requests
from flask import Flask, render_template, request, jsonify
import threading
import time

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Global variables
chat_instance = None
app = Flask(__name__)

# Ollama configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3")

def check_ollama_connection():
    """Check if Ollama is accessible"""
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        return response.status_code == 200
    except Exception as e:
        logging.warning(f"Ollama not available: {e}")
        return False

def synthesize_with_ollama(raw_chunks, question):
    """Use Ollama to create intelligent answers from raw chunks"""
    if not check_ollama_connection():
        return raw_chunks  # Fallback to raw chunks if Ollama unavailable
    
    try:
        # Clean and prepare context from chunks
        context = clean_context(raw_chunks)
        
        # Create intelligent prompt
        prompt = f"""Basandoti esclusivamente sul contesto fornito, rispondi alla domanda in modo chiaro, completo e strutturato.

CONTESTO:
{context}

DOMANDA: {question}

ISTRUZIONI:
- Rispondi solo se l'informazione è presente nel contesto
- Sii preciso e completo
- Organizza la risposta in modo leggibile
- Se nel contesto mancano informazioni, specifica cosa manca
- Non inventare informazioni non presenti nel contesto

RISPOSTA:"""

        # Send to Ollama
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,  # Low temperature for factual responses
                "top_p": 0.9
            }
        }
        
        response = requests.post(f"{OLLAMA_HOST}/api/generate", json=payload, timeout=30)
        
        if response.status_code == 200:
            return response.json().get("response", raw_chunks)
        else:
            logging.error(f"Ollama error: {response.text}")
            return raw_chunks
            
    except Exception as e:
        logging.error(f"Error synthesizing with Ollama: {e}")
        return raw_chunks

def clean_context(raw_chunks):
    """Clean and structure the context from Memvid chunks"""
    if not raw_chunks:
        return "Nessun contesto trovato."
    
    # Split chunks and clean them
    if isinstance(raw_chunks, str):
        # Look for numbered chunks pattern
        chunks = []
        lines = raw_chunks.split('\n')
        current_chunk = ""
        
        for line in lines:
            line = line.strip()
            if line and (line.startswith(('1.', '2.', '3.', '4.', '5.')) or 
                        'Based on the knowledge base' in line):
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line
            else:
                current_chunk += " " + line
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        # Clean individual chunks
        cleaned_chunks = []
        for chunk in chunks:
            # Remove common prefixes and clean
            chunk = chunk.replace('Based on the knowledge base, here\'s what I found:', '')
            chunk = chunk.replace('Based on the knowledge base', '')
            chunk = chunk.strip()
            
            # Remove numbering at start
            if chunk.startswith(('1. ', '2. ', '3. ', '4. ', '5. ')):
                chunk = chunk[3:]
            
            # Only keep substantial chunks
            if len(chunk) > 20:
                cleaned_chunks.append(chunk)
        
        return '\n\n'.join(cleaned_chunks[:3])  # Top 3 most relevant chunks
    
    return str(raw_chunks)

def process_docs():
    """Process documents and create knowledge video"""
    try:
        encoder = MemvidEncoder()
        has_chunks = False
        
        # Process markdown files
        docs_dir = "/app/docs"
        if os.path.exists(docs_dir):
            for file in os.listdir(docs_dir):
                if file.endswith(".md"):
                    filepath = os.path.join(docs_dir, file)
                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            content = f.read()
                            # Improve chunking for better context
                            encoder.add_text(content, metadata={"file": file, "type": "markdown"})
                        logging.info(f"📄 Processed: {file}")
                        has_chunks = True
                    except Exception as e:
                        logging.error(f"Error processing {file}: {e}")
        
        # Process PDF files
        pdfs_dir = "/app/pdfs"
        if os.path.exists(pdfs_dir):
            for file in os.listdir(pdfs_dir):
                if file.endswith(".pdf"):
                    filepath = os.path.join(pdfs_dir, file)
                    try:
                        encoder.add_pdf(filepath)
                        logging.info(f"📚 Processed PDF: {file}")
                        has_chunks = True
                    except Exception as e:
                        logging.error(f"Error processing {file}: {e}")
        
        # Check if we have chunks
        if not has_chunks:
            logging.error("❌ No markdown or PDF files found in /app/docs or /app/pdfs")
            sys.exit(1)
        
        # Build the video
        output_video = "/app/output/knowledge.mp4"
        output_index = "/app/output/knowledge_index.json"
        encoder.build_video(output_video, output_index)
        logging.info("🎬 Knowledge video created!")
        
        return output_video, output_index
    except Exception as e:
        logging.error(f"Error during processing: {e}")
        sys.exit(1)

@app.route('/')
def index():
    """Serve the main HTML page"""
    try:
        return render_template('index.html')
    except Exception as e:
        logging.error(f"Error serving index.html: {e}")
        return f"Error: Could not load index.html. Make sure it exists in the templates/ directory. Error: {e}", 500

@app.route('/ask', methods=['POST'])
def ask():
    """Handle chat requests with selectable modes"""
    global chat_instance
    
    if not chat_instance:
        return jsonify({'error': 'Chat system not initialized. Please restart the application.'}), 500
    
    try:
        data = request.get_json()
        question = data.get('question', '').strip()
        mode = data.get('mode', 'intelligent')  # 'intelligent' or 'mechanical'
        
        if not question:
            return jsonify({'error': 'Empty question'}), 400
        
        logging.info(f"🤔 Question: {question} (Mode: {mode})")
        
        # Get raw chunks from Memvid
        raw_memvid_response = chat_instance.chat(question)
        logging.info(f"📚 Raw Memvid response: {raw_memvid_response}")
        
        if mode == 'mechanical':
            # Mechanical mode: return raw Memvid response
            answer = raw_memvid_response
            logging.info(f"⚙️ Mechanical answer: {answer}")
            response_type = 'mechanical'
        else:
            # Intelligent mode: synthesize with Ollama
            if check_ollama_connection():
                intelligent_answer = synthesize_with_ollama(raw_memvid_response, question)
                logging.info(f"🧠 Intelligent answer: {intelligent_answer}")
                answer = intelligent_answer
                response_type = 'intelligent'
            else:
                # Fallback: clean the raw response
                answer = clean_context(raw_memvid_response)
                answer = f"⚠️ Ollama non disponibile. Risposta pulita dal database:\n\n{answer}"
                logging.warning("Ollama not available, using cleaned raw response")
                response_type = 'warning'
        
        return jsonify({
            'answer': answer,
            'mode': mode,
            'response_type': response_type
        })
    
    except Exception as e:
        logging.error(f"❌ Error processing question: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/status')
def status():
    """Check system status"""
    return jsonify({
        'memvid_ready': chat_instance is not None,
        'ollama_available': check_ollama_connection(),
        'ollama_host': OLLAMA_HOST,
        'ollama_model': OLLAMA_MODEL
    })

def launch_ui():
    """Launch the improved web UI"""
    global chat_instance
    
    try:
        # Process documents first
        logging.info("📚 Processing documents...")
        video_path, index_path = process_docs()
        
        # Initialize chat
        logging.info("🔧 Initializing chat system...")
        chat_instance = MemvidChat(video_path, index_path)
        logging.info("✅ Chat system ready!")
        
        # Check Ollama
        if check_ollama_connection():
            logging.info(f"🧠 Ollama available at {OLLAMA_HOST} with model {OLLAMA_MODEL}")
        else:
            logging.warning("⚠️ Ollama not available - will use basic responses")
        
        # Launch Flask app
        logging.info("🚀 Starting web interface on http://0.0.0.0:7860")
        app.run(host="0.0.0.0", port=7860, debug=False)
        
    except Exception as e:
        logging.error(f"❌ Error launching UI: {e}")
        sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "ui":
        launch_ui()
    else:
        process_docs()