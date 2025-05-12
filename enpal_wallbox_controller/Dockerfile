FROM python:3.10-slim

# Install dependencies for Firefox and Selenium
RUN apt-get update && apt-get install -y \
    firefox-esr \
    wget \
    ca-certificates \
    gnupg \
    libgtk-3-0 \
    libdbus-glib-1-2 \
    libasound2 \
    libnss3 \
    libxss1 \
    libxtst6 \
    libxrandr2 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libglib2.0-0 \
    libfontconfig1 \
    unzip \
    curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Set environment variable for geckodriver version
ENV GECKODRIVER_VERSION=v0.34.0

# Detect architecture and download matching geckodriver binary
RUN ARCH=$(uname -m) && \
    if [ "$ARCH" = "x86_64" ]; then \
        GD_FILE="geckodriver-${GECKODRIVER_VERSION}-linux64.tar.gz"; \
    elif [ "$ARCH" = "aarch64" ]; then \
        GD_FILE="geckodriver-${GECKODRIVER_VERSION}-linux-aarch64.tar.gz"; \
    else \
        echo "Unsupported architecture: $ARCH" && exit 1; \
    fi && \
    wget -q https://github.com/mozilla/geckodriver/releases/download/${GECKODRIVER_VERSION}/$GD_FILE && \
    tar -xzf $GD_FILE -C /usr/bin && \
    chmod +x /usr/bin/geckodriver && \
    rm $GD_FILE

# Set working directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY run.py .

# Expose API port
EXPOSE 36725

# Run script
CMD ["python", "run.py"]

