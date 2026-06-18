"""Launch the interactive text client for the LM Studio streaming example."""
from examples.interactive_streaming.TextClient import TextClient


def main():
    client = TextClient("text-ui", 49999)
    try:
        client.interactive_loop()
    except KeyboardInterrupt:
        client.disconnect()


if __name__ == "__main__":
    main()
