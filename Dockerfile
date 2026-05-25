# Use the official Microsoft Playwright Python image
# This image has Chromium pre-installed at the correct path
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set working directory
WORKDIR /app

# Copy and install Python dependencies first (layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Run the bot
CMD ["python", "bot.py"]
