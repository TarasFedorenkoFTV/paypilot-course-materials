FROM python:3.12-slim

WORKDIR /stand
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY prompts ./prompts
COPY profiles ./profiles
COPY scripts ./scripts
COPY specs ./specs

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
