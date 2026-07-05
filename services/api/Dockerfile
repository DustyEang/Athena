# Athena API — server mode container (see docs/SERVER_ROADMAP.md).
# IMPORTANT: build from the REPO ROOT so plugins/ is inside the build context:
#   docker build -t athena-api -f services/api/Dockerfile .
#   docker run -p 8765:8765 -v athena-data:/data -e ATHENA_DATA_DIR=/data athena-api
FROM python:3.12-slim

WORKDIR /repo/services/api
COPY services/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Preserve the repo layout: config.REPO_ROOT walks up 3 dirs from athena_api/,
# so /repo becomes the root and /repo/plugins is found automatically.
COPY services/api/athena_api ./athena_api
COPY plugins /repo/plugins

ENV ATHENA_DATA_DIR=/data
EXPOSE 8765
CMD ["python", "-m", "uvicorn", "athena_api.main:app", "--host", "0.0.0.0", "--port", "8765"]
