import socket, socketserver, sys, logging, os, threading

host = "0.0.0.0"
port = 10000
address = (host, port)
current = 0
ID = int(os.environ["ID"])

peer_hostnames = os.environ["PEERS"].split(',')


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)-15s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


class TCPHandler(socketserver.BaseRequestHandler):

    def handle(self):
        # import pdb; pdb.set_trace()
        message_bytes = self.request.recv(10).strip()
        logger.info(f'Received {str(message_bytes)}')
        if message_bytes == b"ping":
            self.request.sendall(b"pong")
            logger.info(f'Sent b"pong"')
        schedule_pings()

def serve():
    schedule_pings()
    server = socketserver.TCPServer(address, TCPHandler)
    server.serve_forever()

def ping_peers():
    for hostname in peer_hostnames:
        ping(hostname)
    schedule_pings()

def schedule_pings():
    global current
    current = (current + 1) % 3
    if ID == current:
        threading.Timer(1, ping_peers).start()

def ping(hostname):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        addr = (hostname, port)
        s.connect(addr)
        s.sendall(b"ping")
        logger.info(f'Sent b"ping"')
        data = s.recv(10)
        logger.info(f'Received {str(data)}')


if __name__ == "__main__":
    command = sys.argv[1]
    if command == "serve":
        serve()
    elif command == "ping":
        ping()
    else:
        print("python ping_pong.py <serve|ping>")
