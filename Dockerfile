FROM python:3.12-slim-bookworm

# Prevent Python from writing .pyc files & enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LOG_FORMAT=json
ENV TZ=Asia/Ho_Chi_Minh

WORKDIR /app

# Install system tzdata and set timezone to Vietnam (Asia/Ho_Chi_Minh, GMT+7)
RUN apt-get update && apt-get install -y --no-install-recommends tzdata \
    && ln -fs /usr/share/zoneinfo/Asia/Ho_Chi_Minh /etc/localtime \
    && echo "Asia/Ho_Chi_Minh" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Create log directory
RUN mkdir -p /var/log/email_migrator

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code & configs
COPY src/ ./src/
COPY config/ ./config/

EXPOSE 8000 8080

CMD ["python", "-m", "src.main", "--web", "--port", "8000", "--web-port", "8080"]
