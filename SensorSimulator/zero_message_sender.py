from pythonosc import udp_client
import time
import argparse

class ZeroMessageSender:
    def __init__(self, target_ip, target_port, message_address, frequency, message_length, num_messages):
        """
        Initiate the sender with target address, frequency, message length and number of messages
        """
        self.target_ip = target_ip
        self.target_port = target_port
        self.message_address = message_address
        # Convert frequency to sleep time in seconds
        self.sleep_time = 1 / frequency  
        self.message_length = message_length
        self.num_messages = num_messages
        self.client = udp_client.SimpleUDPClient(target_ip, target_port)

    def send_data(self):
        """
        Send zero-filled messages at the defined frequency for a certain number of times
        """
        zero_message = [0]*self.message_length
        count = 0
        while True:
            self.client.send_message(self.message_address, zero_message)
            time.sleep(self.sleep_time)
            count += 1
            if self.num_messages != 0 and count >= self.num_messages:
                break

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Zero Message Sender')
    parser.add_argument('--ip', type=str, required=True, help='Target IP address')
    parser.add_argument('--port', type=int, required=True, help='Target port')
    parser.add_argument('--addr', type=str, required=True, help='OSC message address')
    parser.add_argument('--freq', type=float, required=True, help='Frequency to send data')
    parser.add_argument('--length', type=int, required=True, help='Length of the zero-filled message')
    parser.add_argument('--num', type=int, default=0, help='Number of messages to send. 0 means infinite.')

    args = parser.parse_args()

    sender = ZeroMessageSender(args.ip, args.port, args.addr, args.freq, args.length, args.num)
    sender.send_data()
