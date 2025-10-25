# 1. Python 3.10 slim version
FROM python:3.10-slim

# 2. System packages update and ffmpeg install
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 3. Set work directory
WORKDIR /app

# 4. Copy all files
COPY . .

# 5. Install Python dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# 6. Expose port (optional for bots, not mandatory)
EXPOSE 8080

# 7. Start your bot
CMD ["python", "app.py"]