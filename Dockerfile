FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.lock requirements.txt ./
RUN pip install --no-cache-dir -r requirements.lock

COPY src ./src
COPY scripts ./scripts
COPY main.py ./main.py

CMD ["python", "main.py"]
