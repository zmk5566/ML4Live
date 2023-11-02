import pandas as pd
import time
import argparse
from pythonosc import udp_client

class SensorSimulator:
    def __init__(self, file_path, target_ip, target_port, message_address, frequency, loop):
        """
        Initiate the simulator with CSV file path, target address, frequency and loop option
        """
        self.file_path = file_path
        self.target_ip = target_ip
        self.target_port = target_port
        self.message_address = message_address
        # Convert frequency to sleep time in seconds
        self.sleep_time = 1 / frequency  
        self.loop = loop
        self.data = None
        self.client = udp_client.SimpleUDPClient(target_ip, target_port)

    def read_csv_file(self):
        """
        Read CSV file and store values
        """
        self.data = pd.read_csv(self.file_path).values.tolist()

    def send_data(self):
        """
        Send data line by line at the defined frequency, possibly in a loop
        """
        if self.data is not None:
            while True:
                for line in self.data:
                    self.client.send_message(self.message_address, line)
                    time.sleep(self.sleep_time)
                if not self.loop:
                    break
        else:
            print("No data to send. Please read the CSV file first.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Sensor Simulator')
    parser.add_argument('--file', type=str, required=True, help='Path to the CSV file')
    parser.add_argument('--ip', type=str, required=True, help='Target IP address')
    parser.add_argument('--port', type=int, required=True, help='Target port')
    parser.add_argument('--addr', type=str, required=True, help='OSC message address')
    parser.add_argument('--freq', type=float, required=True, help='Frequency to send data')
    parser.add_argument('--loop', type=bool, default=False, help='Whether to loop the data')

    args = parser.parse_args()

    simulator = SensorSimulator(args.file, args.ip, args.port, args.addr, args.freq, args.loop)
    simulator.read_csv_file()
    simulator.send_data()