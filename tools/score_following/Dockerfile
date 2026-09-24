FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml constraints-py313.txt ./
COPY scorefollow ./scorefollow
RUN python -m pip install -c constraints-py313.txt . && useradd --uid 10001 --no-create-home app
USER 10001:10001
EXPOSE 8765/tcp
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/healthz',timeout=2).read()"
CMD ["python", "-m", "scorefollow", "serve", "--host", "0.0.0.0"]
