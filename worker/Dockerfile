FROM python:3.12-slim
WORKDIR /app
COPY api/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY . .
CMD ["celery","-A","worker.tasks:celery","worker","--loglevel=info"]
