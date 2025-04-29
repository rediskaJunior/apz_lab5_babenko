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

import messages_pb2
import messages_pb2_grpc
from consul_helper import register_service, get_list_from_consul, get_value_from_consul

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MessageService(messages_pb2_grpc.MessageServiceServicer):
    def __init__(self, cluster_members, hazelcast_cluster_name):
        self.messages = []
        self.config = Config()
        self.config.cluster_name = hazelcast_cluster_name
        self.config.cluster_members = cluster_members
        self.client = hazelcast.HazelcastClient(self.config)
        queue_name = get_value_from_consul(os.getenv('QUEUE_NAME_KEY'), os.getenv('CONSUL_HOST'), int(os.getenv('CONSUL_PORT')))
        self.queue = self.client.get_queue(queue_name).blocking()

        self.consumer_thread = threading.Thread(target=self.consume_messages, daemon=True)
        self.consumer_thread.start()

    def consume_messages(self):
        while True:
            try:
                msg = self.queue.poll(timeout=5)
                if msg is not None:
                    logger.info(f"Consumed message: {msg}")
                    self.messages.append(msg)
                else:
                    time.sleep(1)
            except Exception as e:
                logger.error(f"Error consuming message: {e}")
                time.sleep(1)

    def GetStaticMessage(self, request, context):
        return messages_pb2.MessageResponse(message="Message Service is ready")

    def GetAllMessages(self, request, context):
        return messages_pb2.MessageList(messages=self.messages)

def serve(port, cluster_members, hazelcast_cluster_name):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    messages_pb2_grpc.add_MessageServiceServicer_to_server(MessageService(cluster_members, hazelcast_cluster_name), server)

    SERVICE_NAMES = (
        messages_pb2.DESCRIPTOR.services_by_name["MessageService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(SERVICE_NAMES, server)

    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f"Message Service is alive on gRPC port {port}")
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
    register_service("messages-service", grpc_port, flask_port, consul_host, consul_port)

    cluster_members = get_list_from_consul(hazelcast_address_key, consul_host, consul_port)
    hazelcast_cluster_name = get_value_from_consul(hazelcast_cluster_name_key, consul_host, consul_port)

    threading.Thread(target=serve, args=(grpc_port, cluster_members, hazelcast_cluster_name), daemon=True).start()
    app.run(host="0.0.0.0", port=flask_port)
