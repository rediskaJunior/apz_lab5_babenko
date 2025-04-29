import requests
import socket
import base64

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

def get_list_from_consul(key_prefix, consul_host='localhost', consul_port=8500):
    url = f"http://{consul_host}:{consul_port}/v1/kv/{key_prefix}?recurse=true"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        values = [base64.b64decode(item['Value']).decode() for item in data]
        return values
    except Exception as e:
        print(f"Error fetching list from Consul: {e}")
        return []

def get_value_from_consul(key, consul_host='localhost', consul_port=8500):
    url = f"http://{consul_host}:{consul_port}/v1/kv/{key}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        value = base64.b64decode(data[0]['Value']).decode()
        return value
    except Exception as e:
        print(f"Error fetching value from Consul: {e}")
        return None
        
        time.sleep(retry_interval)
    
    raise Exception(f"Service '{service_name}' not found in Consul after {timeout} seconds.")
