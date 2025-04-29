FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

COPY logger.py .
COPY requirements.txt .
COPY logging_pb2.py .
COPY logging_pb2_grpc.py .
COPY consul_helper.py .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "logger.py"]
