import json
from flask import Flask, jsonify
import sys

app = Flask(__name__)

@app.route('/get_ports', methods=['GET'])
def get_ports():
    try:
        with open(sys.argv[2], 'r') as f:
            config_data = json.load(f)
            logging_ports = config_data.get('logging-services', [])
            message_port = config_data.get('message-service', [])
            if not logging_ports or not message_port:
                return jsonify({"error": "Ports configuration is missing or incorrect"}), 400
            return jsonify({"logging-services": logging_ports, "message-service": message_port})
    except Exception as e:
        return jsonify({"error": f"Failed to load config file: {e}"}), 500


def run():
    if len(sys.argv) < 3:
        print("Usage: python config_server.py <listen_port> <config_file_path>")
        sys.exit(1)

    app.run(host='0.0.0.0', port=int(sys.argv[1]))


if __name__ == '__main__':
    run()
