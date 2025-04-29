FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

COPY messages.py .
COPY requirements.txt .
COPY messages_pb2.py .
COPY messages_pb2_grpc.py .
COPY consul_helper.py .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "messages.py"]
