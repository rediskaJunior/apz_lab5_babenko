import requests
import socket

def register_service(service_name, service_port, flask_port, consul_host='localhost', consul_port=8500):
    service_id = f"{service_name}-{socket.gethostname()}-{service_port}"
    url = f"http://{consul_host}:{consul_port}/v1/agent/service/register"
    payload = {
        "Name": service_name,
        "ID": service_id,
        "Address": socket.gethostbyname(socket.gethostname()),
        "Port": service_port,
        "Check": {
            "HTTP": f"http://{socket.gethostbyname(socket.gethostname())}:{flask_port}/health",
            "Interval": "10s"
        }
    }
    response = requests.put(url, json=payload)
    response.raise_for_status()

def discover_service(service_name, consul_host='localhost', consul_port=8500):
    url = f"http://{consul_host}:{consul_port}/v1/health/service/{service_name}?passing"
    response = requests.get(url)
    response.raise_for_status()
    data = response.json()
    
    # Повертаємо список адрес доступних сервісів
    services = []
    for service in data:
        address = service["Service"]["Address"]
        port = service["Service"]["Port"]
        services.append((address, port))
    return services
