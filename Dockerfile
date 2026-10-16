# Built by GitHub Actions only (.github/workflows/image.yml). Dockhand pulls the result.
FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY server ./server
COPY web ./web

EXPOSE 8080
CMD ["uvicorn", "server.web:app", "--host", "0.0.0.0", "--port", "8080"]
