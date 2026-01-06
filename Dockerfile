FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1
ENV PIP_DEFAULT_TIMEOUT=120

COPY requirements.txt .

# pip با retry و timeout بالا
RUN pip install --upgrade pip && \
    pip install --retries 10 --timeout 120 -r requirements.txt

COPY . .

CMD ["python", "main.py"]
