FROM python:3.12-slim
WORKDIR /service
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY requirements-transformer.txt .
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.11.0 \
    && pip install --no-cache-dir -r requirements-transformer.txt
COPY app ./app
COPY data ./data
EXPOSE 8001
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=12 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health/ready', timeout=4)"
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8001"]
