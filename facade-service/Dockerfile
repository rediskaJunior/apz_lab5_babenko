FROM python:3.11-slim

WORKDIR /app

COPY facade.py .
COPY requirements.txt .
COPY logging_pb2.py .
COPY logging_pb2_grpc.py .
COPY facade_pb2.py .
COPY facade_pb2_grpc.py .
COPY messages_pb2.py .
COPY messages_pb2_grpc.py .
COPY consul_helper.py .

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "facade.py"]
