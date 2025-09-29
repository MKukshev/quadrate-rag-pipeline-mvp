
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libglib2.0-0 libgl1 libxml2 libxslt1.1 libjpeg62-turbo curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
ENV PYTHONPATH=/app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# copy entire repo (so CLI and docs are available inside контейнера at /app)
COPY . /app

EXPOSE 8000
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
