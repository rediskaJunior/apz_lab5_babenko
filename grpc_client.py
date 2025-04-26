import grpc
import logging_pb2
import logging_pb2_grpc
import facade_pb2
import facade_pb2_grpc
import sys
import uuid

def send_message_to_facade_service(port, message):
    """Sends a message to the FacadeService."""
    try:
        channel = grpc.insecure_channel(f'localhost:{port}')
        stub = facade_pb2_grpc.FacadeServiceStub(channel)

        request = logging_pb2.LogRequest(uuid=str(uuid.uuid4()), message=message)

        response = stub.WriteMessage(request)

        print(f"Response: Success={response.success}, Message='{response.message}'")

    except grpc.RpcError as e:
        print(f"Error: {e.code()} - {e.details()}")

def get_messages_from_facade_service(port):
    """Retrieves messages from the FacadeService (GET)."""
    try:
        channel = grpc.insecure_channel(f'localhost:{port}')
        stub = facade_pb2_grpc.FacadeServiceStub(channel)

        request = logging_pb2.GetRequest()

        response = stub.ShowMessages(request)

        print("Received Messages:")
        for msg in response.messages:
            print(msg)

    except grpc.RpcError as e:
        print(f"Error: {e.code()} - {e.details()}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python send_message.py <port> <GET|POST> [<message>]")
        sys.exit(1)

    port = sys.argv[1]
    request_type = sys.argv[2].upper()  # Either "GET" or "POST"

    if request_type == "POST" and len(sys.argv) > 3:
        message = " ".join(sys.argv[3:])
        send_message_to_facade_service(port, message)
    elif request_type == "GET":
        get_messages_from_facade_service(port)
    else:
        print("Invalid arguments.")
        sys.exit(1)

