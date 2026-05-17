# Dockerfile per Memvid - Compressione testo in video con QR codes
FROM python:3.11-slim-bookworm

# Metadata
LABEL maintainer="memvid-user"
LABEL description="Memvid - Turn millions of text chunks into a single, searchable video file"
LABEL version="1.0"

# Variabili d'ambiente
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive \
    HF_HOME=/app/data/.cache

# Installa dipendenze di sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libavcodec-extra \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev \
    libavfilter-dev \
    libavdevice-dev \
    pkg-config \
    build-essential \
    git \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Crea directory di lavoro
WORKDIR /app

# Copia e installa dipendenze Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt || { echo "Errore nell'installazione delle dipendenze"; exit 1; }

# Copia gli script
COPY py/*.py ./
COPY templates ./templates
RUN chmod +x *.py

# Crea directory per i dati
RUN mkdir -p /app/data /app/output /app/docs /app/pdfs

# Esponi porta per web UI
EXPOSE 7860

# Volume per persistenza dati
VOLUME ["/app/data", "/app/output", "/app/docs", "/app/pdfs"]

# Crea utente non-root
RUN useradd -m -u 1000 appuser
USER appuser

# Comando di default
CMD ["/bin/bash"]