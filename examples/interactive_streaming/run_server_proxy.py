"""Launch the gRPC server and LM proxy client for the interactive streaming example."""
import threading
import time

from examples.interactive_streaming.GrpcServerExample import GrpcServer
from examples.interactive_streaming.LMProxyClient import LMProxyClient


def main():
    server = GrpcServer(49999)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # start LM proxy client (connects automatically)
    proxy = LMProxyClient("lm-proxy", 49999)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        proxy.disconnect()
        server.shutdown()


if __name__ == "__main__":
    main()
