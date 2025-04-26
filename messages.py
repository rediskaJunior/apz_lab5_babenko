import grpc
from concurrent import futures
import logging
import messages_pb2
import messages_pb2_grpc
from grpc_reflection.v1alpha import reflection
import hazelcast

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MessageService(messages_pb2_grpc.MessageServiceServicer):
    def __init__(self):
        self.messages = []
        self.client = hazelcast.HazelcastClient()
        self.queue = self.client.get_queue("messages-queue").blocking()

        import threading
        self.consumer_thread = threading.Thread(target=self.consume_messages, daemon=True)
        self.consumer_thread.start()

    def consume_messages(self):
        while True:
            try:
                msg = self.queue.take()
                logging.info(f"Consumed message: {msg}")
                self.messages.append(msg)
            except Exception as e:
                logging.error(f"Error consuming message: {e}")
                time.sleep(1)

    def GetStaticMessage(self, request, context):
        return messages_pb2.MessageResponse(message="Message Service is ready")

    def GetAllMessages(self, request, context):
        return messages_pb2.MessageList(messages=self.messages)


def serve(port):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    messages_pb2_grpc.add_MessageServiceServicer_to_server(MessageService(), server)
    
    SERVICE_NAMES = (
        messages_pb2.DESCRIPTOR.services_by_name["MessageService"].full_name,
        reflection.SERVICE_NAME,
    )
    reflection.enable_server_reflection(SERVICE_NAMES, server)

    # Correctly format the port by using an f-string
    server.add_insecure_port(f'[::]:{port}')
    server.start()
    logger.info(f"Message Service is alive on port {port}")
    server.wait_for_termination()

if __name__ == "__main__":
    import sys
    # Ensure the port is passed as an argument, default to "9000"
    port = sys.argv[1] if len(sys.argv) > 1 else "9000"
    serve(port)

