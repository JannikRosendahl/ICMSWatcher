FROM python:3.11-slim

# Install dependencies
RUN apt-get update && \
    apt-get install -y wget unzip curl gnupg2 cron && \
    # Install Chrome
    wget -O /tmp/google-chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get install -y /tmp/google-chrome.deb && \
    rm /tmp/google-chrome.deb && \
    # Get Chrome version
    CHROME_VERSION=$(google-chrome --version | awk '{print $3}') && \
    # Download matching ChromeDriver
    wget -O /tmp/chromedriver.zip "https://storage.googleapis.com/chrome-for-testing-public/$CHROME_VERSION/linux64/chromedriver-linux64.zip" && \
    unzip /tmp/chromedriver.zip -d /usr/local/bin/ && \
    mv /usr/local/bin/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver && \
    chmod +x /usr/local/bin/chromedriver && \
    rm -rf /tmp/chromedriver.zip /usr/local/bin/chromedriver-linux64 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Install uv
RUN pip install --no-cache-dir uv

# Copy pyproject.toml and uv.lock (if it exists)
COPY pyproject.toml .
COPY uv.lock . 2>/dev/null || true

# Install dependencies using uv
RUN uv sync --frozen

# Copy the rest of the application code
COPY . .

# Create logs directory
RUN mkdir -p /app/logs

# Copy entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Command to run the application
CMD ["/usr/local/bin/docker-entrypoint.sh"]