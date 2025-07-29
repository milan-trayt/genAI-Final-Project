FROM python:3.11-slim

WORKDIR /workspace

# Install system dependencies including Chrome for Selenium
RUN apt-get update && apt-get install -y \
    curl \
    git \
    wget \
    gnupg \
    unzip \
    && wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY requirements_socketio.txt .
RUN pip install --no-cache-dir -r requirements_socketio.txt
RUN pip install jupyter

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /workspace/data

# Copy and make startup script executable
COPY start.sh /workspace/start.sh
RUN chmod +x /workspace/start.sh

# Expose ports
EXPOSE 8888 8503

# Run both Jupyter and Streamlit
CMD ["bash", "/workspace/start.sh"]
