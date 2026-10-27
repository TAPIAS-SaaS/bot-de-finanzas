FROM python:3.11-slim

WORKDIR /app/trading_engine

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/trading_engine/src \
    TRADING_MODE=paper \
    ALLOW_LIVE_TRADING=false

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY tests/ ./tests/

RUN useradd --create-home --shell /bin/bash botuser && \
    mkdir -p /app/data && chown -R botuser:botuser /app
USER botuser

EXPOSE 8000

CMD ["python3", "-m", "trading_bot.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]
