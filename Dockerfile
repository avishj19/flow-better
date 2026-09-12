FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY backend ./backend
COPY frontend ./frontend
COPY dist ./dist
RUN useradd --create-home app && mkdir /data && chown app:app /data
USER app
ENV IROP_DATA=/data
EXPOSE 8011
CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8011", "--workers", "1"]
