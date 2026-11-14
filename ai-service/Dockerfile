FROM python:3.12-slim
WORKDIR /service
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY data ./data
COPY scripts ./scripts
RUN python scripts/train_cpu_noise_candidate.py --count 1024
EXPOSE 8001
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8001/health/live')"
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8001"]
