import os
import time
import threading
import logging
import grpc
from concurrent import futures
from flask import Flask
import hazelcast
from hazelcast.config import Config
from grpc_reflection.v1alpha import reflection

import logging_pb2
import logging_pb2_grpc
from consul_helper import register_service, get_list_from_consul, get_value_from_consul

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LoggingService(logging_pb2_grpc.LoggingServiceServicer):
    def __init__(self, hazelcast_client):
        queue_name = get_value_from_consul(os.getenv('QUEUE_NAME_KEY'), os.getenv('CONSUL_HOST'), int(os.getenv('CONSUL_PORT')))
        self.queue = hazelcast_client.get_queue(queue_name).blocking()

    def LogMessage(self, request, context):
        self.queue.offer(f"{request.uuid}:{request.message}")
        size = self.queue.size()
        logger.info(f"Queued message: {request.uuid} -> {request.message} (Queue size: {size})")
        return logging_pb2.LogResponse(success=True, message=f"Queued message with UUID: {request.uuid}")

    def GetMessages(self, request, context):
        messages = []
        while True:
            try:
                message = self.queue.poll(timeout=1)
                if message is None:
                    break
                messages.append(message)
            except Exception as e:
                logger.error(f"Error while polling message: {e}")
                break
        return logging_pb2.GetResponse(messages=messages)

def serve(port, cluster_members, hazelcast_cluster_name):
    config = Config()
    config.cluster_name = hazelcast_cluster_name
    config.cluster_members = cluster_members
    hazelcast_client = hazelcast.HazelcastClient(config)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    logging_pb2_grpc.add_LoggingServiceServicer_to_server(LoggingService(hazelcast_client), server)

    SERVICE_NAMES = (
        logging_pb2.DESCRIPTOR.services_by_name["LoggingService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(SERVICE_NAMES, server)

    server.add_insecure_port(f"[::]:{port}")
    server.start()
    logger.info(f"Logging Service is alive on gRPC port {port}")
    server.wait_for_termination()

@app.route("/", methods=["GET"])
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
    hazelcast_address_key = os.getenv('HAZELCAST_ADRESS_KEY')
    hazelcast_cluster_name_key = os.getenv('HAZELCAST_CLUSTER_NAME_KEY')
    queue_name_key = os.getenv('QUEUE_NAME_KEY')

    if any(v is None for v in [flask_port_str, grpc_port_str, consul_port_str, consul_host, hazelcast_address_key, hazelcast_cluster_name_key, queue_name_key]):
        raise ValueError("Missing required environment variables: FLASK_PORT, PORT, CONSUL_PORT, CONSUL_HOST, HAZELCAST_ADRESS_KEY, HAZELCAST_CLUSTER_NAME_KEY, QUEUE_NAME_KEY")

    try:
        flask_port = int(flask_port_str)
        grpc_port = int(grpc_port_str)
        consul_port = int(consul_port_str)
    except ValueError:
        raise ValueError("Environment variables FLASK_PORT, PORT, and CONSUL_PORT must be integers")

    app.config["SERVICE_PORT"] = grpc_port
    register_service("logging-service", grpc_port, flask_port, consul_host, consul_port)

    cluster_members = get_list_from_consul(hazelcast_address_key, consul_host, consul_port)
    hazelcast_cluster_name = get_value_from_consul(hazelcast_cluster_name_key, consul_host, consul_port)

    threading.Thread(target=serve, args=(grpc_port, cluster_members, hazelcast_cluster_name), daemon=True).start()
    app.run(host="0.0.0.0", port=flask_port)
