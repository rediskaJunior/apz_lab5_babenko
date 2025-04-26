import grpc
import hazelcast
import random
import time
import uuid
from concurrent import futures
import logging
import logging_pb2
import logging_pb2_grpc
from grpc_reflection.v1alpha import reflection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LoggingService(logging_pb2_grpc.LoggingServiceServicer):
    def __init__(self, hazelcast_client):
        self.queue = hazelcast_client.get_queue("messages-queue").blocking()
    
    def LogMessage(self, request, context):
        self.queue.offer(f"{request.uuid}:{request.message}")
        logger.info(f"Queued message: {request.uuid} -> {request.message}")
        return logging_pb2.LogResponse(success=True, message=f"Queued message with UUID: {request.uuid}")

    def GetMessages(self, request, context):
        return logging_pb2.GetResponse(messages=[])

def serve(port):
    hazelcast_client = hazelcast.HazelcastClient()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    logging_pb2_grpc.add_LoggingServiceServicer_to_server(LoggingService(hazelcast_client), server)
    
    SERVICE_NAMES = (
        logging_pb2.DESCRIPTOR.services_by_name["LoggingService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(SERVICE_NAMES, server)
    
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    logger.info(f"Logging Service is alive on port {port}")
    server.wait_for_termination()

if __name__ == "__main__":
    import sys
    port = sys.argv[1] if len(sys.argv) > 1 else "8001"
    serve(port)
