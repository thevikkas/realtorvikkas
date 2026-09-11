FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy application files
COPY . /app

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 10000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:10000/command-center')" || exit 1

# Run application
CMD ["python3", "app.py"]
