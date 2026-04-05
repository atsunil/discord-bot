FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose the ping server port for Hugging Face / UptimeRobot
EXPOSE 8080

# Start the bot
CMD ["python", "bot.py"]
