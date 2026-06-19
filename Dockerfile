# ourdigest — small Python image, no surprises
FROM python:3.12-slim

WORKDIR /app

# system deps kept minimal; tini for clean signal handling
RUN apt-get update && apt-get install -y --no-install-recommends tini ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir -e .

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8088

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["ourdigest", "serve", "--host", "0.0.0.0", "--port", "8088"]
