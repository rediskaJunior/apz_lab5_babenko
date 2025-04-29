import grpc
import random
import time
import uuid
import os
from concurrent import futures
from flask import Flask, request, jsonify
from grpc_reflection.v1alpha import reflection

import logging_pb2
import logging_pb2_grpc
import facade_pb2
import facade_pb2_grpc
import messages_pb2
import messages_pb2_grpc
from consul_helper import register_service, discover_service

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_messages_stub():
    consul_port = int(os.getenv('CONSUL_PORT'))
    consul_host = os.getenv('CONSUL_HOST')
    services = discover_service("messages-service", consul_host, consul_port)
    random.shuffle(services)
    for address, port in services:
        try:
            channel = grpc.insecure_channel(f"{address}:{port}")
            grpc.channel_ready_future(channel).result(timeout=1)
            return messages_pb2_grpc.MessageServiceStub(channel)
        except Exception as e:
            logger.error(f"Failed to connect to messages service at {address}:{port}: {e}")
    return None

def get_logging_stub():
    consul_port = int(os.getenv('CONSUL_PORT'))
    consul_host = os.getenv('CONSUL_HOST')
    services = discover_service("logging-service", consul_host, consul_port)
    random.shuffle(services)
    for address, port in services:
        try:
            channel = grpc.insecure_channel(f"{address}:{port}")
            grpc.channel_ready_future(channel).result(timeout=1)
            return logging_pb2_grpc.LoggingServiceStub(channel)
        except Exception as e:
            logger.error(f"Failed to connect to logging service at {address}:{port}: {e}")
    return None

class FacadeService(facade_pb2_grpc.FacadeServiceServicer):
    def WriteMessage(self, request, context):
        message_uuid = str(uuid.uuid4())
        stub = get_logging_stub()
        if not stub:
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details("No available logging services.")
            return facade_pb2.LogResponse(success=False, message="No logging service available")
        try:
            log_request = logging_pb2.LogRequest(uuid=message_uuid, message=request.message)
            return stub.LogMessage(log_request)
        except grpc.RpcError as e:
            logger.error(f"Logging service error: {e}")
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details("Logging service unavailable.")
            return facade_pb2.LogResponse(success=False, message="Failed to log message")

    def ShowMessages(self, request, context):
        logging_stub = get_logging_stub()
        messages_stub = get_messages_stub()
        try:
            log_response = []
            if logging_stub:
                log_response = logging_stub.GetMessages(logging_pb2.GetRequest()).messages
            static_message_response = ""
            if messages_stub:
                static_message_response = messages_stub.GetStaticMessage(messages_pb2.EmptyRequest()).message
            all_messages_response = []
            if messages_stub:
                all_messages_response = messages_stub.GetAllMessages(messages_pb2.EmptyRequest()).messages
            formatted_response = " ".join([f"{{ {log_msg} }}" for log_msg in log_response]) + f" : {{ {static_message_response} }}" + " ".join([f"{{ {cons_msg} }}" for cons_msg in all_messages_response])
            return logging_pb2.GetResponse(messages=[formatted_response])
        except grpc.RpcError as e:
            logger.error(f"Error fetching messages: {e}")
            context.set_code(grpc.StatusCode.UNAVAILABLE)
            context.set_details("Failed to fetch messages.")
            return facade_pb2.GetResponse(messages=[])

def serve(grpc_port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    facade_pb2_grpc.add_FacadeServiceServicer_to_server(FacadeService(), server)
    SERVICE_NAMES = (
        facade_pb2.DESCRIPTOR.services_by_name['FacadeService'].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(SERVICE_NAMES, server)
    server.add_insecure_port(f'[::]:{grpc_port}')
    server.start()
    logger.info(f"Facade Service gRPC server is alive on port {grpc_port}")
    server.wait_for_termination()

app = Flask(__name__)

@app.route("/write", methods=["POST"])
def write_message():
    data = request.get_json()
    message = data.get("message")
    if not message:
        return jsonify({"error": "Missing 'message' field"}), 400
    grpc_port = app.config.get("SERVICE_PORT")
    with grpc.insecure_channel(f"localhost:{grpc_port}") as channel:
        stub = facade_pb2_grpc.FacadeServiceStub(channel)
        try:
            response = stub.WriteMessage(facade_pb2.MessageRequest(message=message))
            return jsonify({"success": response.success, "message": response.message})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route("/show_messages", methods=["GET"])
def show_messages():
    grpc_port = app.config.get("SERVICE_PORT")
    with grpc.insecure_channel(f"localhost:{grpc_port}") as channel:
        stub = facade_pb2_grpc.FacadeServiceStub(channel)
        try:
            response = stub.ShowMessages(facade_pb2.ShowRequest())
            return jsonify({"messages": list(response.messages)}), 200
        except Exception as e:
            return jsonify({"error": str(e)}), 500

@app.route("/health", methods=["GET"])
def health():
    return "OK", 200

if __name__ == "__main__":
    wait_to_start_str = os.getenv('WAIT_TO_START')
    wait_to_start = 5
    if wait_to_start_str is not None:
        try:
            wait_to_start = int(wait_to_start_str)
        except ValueError:
            raise ValueError("WAIT_TO_START environment variable must be an integer")
    time.sleep(wait_to_start)

    flask_port_str = os.getenv('FLASK_PORT')
    grpc_port_str = os.getenv('PORT')
    consul_port_str = os.getenv('CONSUL_PORT')
    consul_host = os.getenv('CONSUL_HOST')

    if any(v is None for v in [flask_port_str, grpc_port_str, consul_port_str, consul_host]):
        raise ValueError("One or more required environment variables are not set: FLASK_PORT, PORT, CONSUL_PORT, CONSUL_HOST")

    try:
        flask_port = int(flask_port_str)
        grpc_port = int(grpc_port_str)
        consul_port = int(consul_port_str)
    except ValueError as e:
        raise ValueError("One of the port environment variables is not an integer") from e

    app.config["SERVICE_PORT"] = grpc_port
    register_service("facade-service", grpc_port, flask_port, consul_host, consul_port)

    from threading import Thread
    Thread(target=serve, args=(grpc_port,), daemon=True).start()
    app.run(host="0.0.0.0", port=flask_port)
