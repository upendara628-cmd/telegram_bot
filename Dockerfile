# Use the official Microsoft Playwright Python image (v1.44.0)
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

# CRITICAL: Tell Playwright where browsers are in this Docker image
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Run the bot
CMD ["python", "bot.py"]
