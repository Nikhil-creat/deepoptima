FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app ./app
RUN useradd -m app && chown -R app /srv
USER app
CMD ["uvicorn","app.api.main:app","--host","0.0.0.0","--port","8000"]
