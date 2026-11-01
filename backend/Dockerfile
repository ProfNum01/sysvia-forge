FROM python:3.13-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY proofsight ./proofsight
COPY scripts ./scripts
COPY evaluation/manifests/synthetic-packing.json ./evaluation/manifests/synthetic-packing.json
COPY evaluation/datasets/synthetic-packing ./evaluation/datasets/synthetic-packing
COPY evaluation/datasets/synthetic-claude-labeled ./evaluation/datasets/synthetic-claude-labeled
COPY evaluation/datasets/ten-orders ./evaluation/datasets/ten-orders
RUN useradd --create-home proofsight && mkdir /app/data && chown proofsight /app/data
USER proofsight
EXPOSE 8000
CMD ["sh", "-c", "python scripts/seed_demo.py && uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --workers 1"]
