#!/usr/bin/env python3
from memvid import MemvidEncoder, MemvidChat
import os

print("🚀 Memvid Docker Container Ready!")
print("Testing basic functionality...")

# Test basico
chunks = [
    "Docker container per Memvid funzionante",
    "QR codes compressi in video MP4",
    "Ricerca semantica millisecondo-level"
]

try:
    encoder = MemvidEncoder()
    encoder.add_chunks(chunks)
    encoder.build_video("/app/output/test.mp4", "/app/output/test_index.json")
    
    chat = MemvidChat("/app/output/test.mp4", "/app/output/test_index.json")
    response = chat.chat("Come funziona Memvid?")
    print(f"✅ Test completato! Risposta: {response}")
except Exception as e:
    print(f"❌ Errore: {e}")
    print("Verifica le dipendenze video")
