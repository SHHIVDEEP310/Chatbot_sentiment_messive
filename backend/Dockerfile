FROM python:3.11-slim

WORKDIR /srv
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# Tesseract = OCR engine used to extract text from uploaded photos/videos;
# libglib2.0-0 is needed by OpenCV.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

# CPU-only torch keeps the image far smaller than the default CUDA build.
COPY requirements.txt .
RUN pip install torch==2.4.1 --index-url https://download.pytorch.org/whl/cpu \
 && pip install -r requirements.txt

COPY app ./app

# Mount or bake your HuggingFace checkpoint at /model (see MODEL_PATH).
ENV MODEL_PATH=/model
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
