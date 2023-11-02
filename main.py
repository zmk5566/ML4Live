from pythonosc import udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer
from sklearn.neighbors import KNeighborsClassifier
import numpy as np
import asyncio
import websockets
import json
import time
from joblib import dump, load
import threading
from enum import Enum, auto

class SystemStatus(Enum):
    STANDBY = auto()
    PREDICTING = auto()
    TRAINING = auto()
    STOPPED = auto()


class PastBuffer:
    def __init__(self, max_size, array_shape):
        self.buffer = np.zeros((max_size, *array_shape))
        self.max_size = max_size
        self.array_shape = array_shape
        self.current_size = 0

    def add(self, np_array):
        if self.current_size < self.max_size:
            self.buffer[self.current_size] = np_array
            self.current_size += 1
        else:
            # Roll the buffer to remove the oldest entry and create space at the end.
            self.buffer = np.roll(self.buffer, -1, axis=0)
            
            # Insert the new array at the end
            self.buffer[-1] = np_array

    def getBuffer(self):
        return self.buffer

    def isEmpty(self):
        return self.current_size == 0



class MLProcessing:
    def __init__(self, input_osc_address, output_osc_address,osc_input_topic,osc_output_topic, osc_port, output_number,websocket_port,buffer_size=1):
        self.input_osc_address = input_osc_address
        self.output_osc_address = output_osc_address
        self.osc_port = osc_port
        self.websocket_port = websocket_port
        self.status = SystemStatus.STOPPED
        self.osc_input_topic = osc_input_topic
        self.osc_output_topic = osc_output_topic
        self.output_number = output_number
        self.msg_counter = 0
        self.websocket = None
        self.buffer_size = buffer_size


        # Initialize machine learning model
        self.model = KNeighborsClassifier()

        # Create dispatcher for incoming OSC signals
        self.dispatcher = Dispatcher()
        self.dispatcher.map(osc_input_topic, self.process)

        # Create client for outgoing OSC signals
        self.client = udp_client.SimpleUDPClient(self.output_osc_address, self.osc_port)

        # Initialize training variables
        self.start_sampling = False
        self.training = False
        self.is_training_complete = False
        self.trainning_data_x = []
        self.trainning_data_y = []
        self.temp_buffer = []
        self.past_data = PastBuffer(self.buffer_size, (3,))
    
    def update_processing(self, input_osc_address, output_osc_address,osc_input_topic,osc_output_topic, osc_port,output_number):

        self.input_osc_address = input_osc_address
        self.osc_input_topic = osc_input_topic
        self.output_osc_address = output_osc_address
        self.osc_port = osc_port
        self.osc_output_topic = osc_output_topic
        self.output_number = output_number
        # TODO : IT NEED TO BE PROPER IMPLEMENTED LATER. IT SHOULD STOP THE OSC CLIENT AND SERVER AND RESTART IT WITH THE NEW CONFIGURATION 


    def listen(self):
        self.osc_server = BlockingOSCUDPServer((self.input_osc_address, self.osc_port), self.dispatcher)
        print(f"Listening for OSC on {self.osc_server.server_address}")

        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(websockets.serve(self.websocket_handler, "localhost", self.websocket_port))
        # run the loop forever, in the background

        # create an async task to run the loop
        
        try:
            self.loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            print("Closing asyncio loop.")
            self.loop.close()


        self.osc_server.shutdown()
        self.osc_thread.join()


    def initialize_osc_server(self):
        self.status = SystemStatus.STANDBY
        self.osc_thread = threading.Thread(target=self.osc_server.serve_forever)
        self.osc_thread.start()

    def maintain_buffer(self, data):
        # Maintain a buffer of past data
        if len(self.past_data) < self.buffer_size:
            self.past_data = np.append(self.past_data, data)
        else:
            self.past_data = np.append(self.past_data, data)
            self.past_data = np.delete(self.past_data, 0)

    async def websocket_handler(self, websocket, path):
        self.websocket = websocket
        while True:
            message = await websocket.recv()
            print(f"< {message}")

            # Parse the incoming WebSocket message and adjust processing as needed

            # process the message with try catch
            try:
                self.process_websocket_message(message)
            except Exception as e:
                print("Error in processing the message")
                print(e)
                self.simple_send_websocket_message("Error in processing the message",message_type="error")

    def process(self, unused_addr,*args):
        # Process incoming OSC signal
        #print("From {}: Received message: {}".format(unused_addr, args))
        data = np.array(args)  # convert args to numpy array for further processing
        #print(data)

        self.past_data.add(data)
        #self.maintain_buffer(data)
        #iltered_data = self.filter_data(data)

    def filter_data(self, data, filter_type="none", filter_windows_size=10):
        # Implement your filter here
        # several filters are available
        # 1. none
        # 2. mean
        if filter_type == "none":
            return data
        
        elif filter_type == "mean":
            if len(self.past_data) < filter_windows_size:
                return data
            else:
                return np.mean(self.past_data[-filter_windows_size:], axis=0)

        return data

    def train(self, data,model_type="KNN"):
        # Implement your training function here
        # start training
        if model_type == "KNN":
            self.model = KNeighborsClassifier(n_neighbors=3)
            # start training using the training data x and y
            # singal to the websocket that training is started 

            self.model.fit(self.trainning_data_x, self.trainning_data_y)
            self.is_training_complete = True

    def construct_status_json(self):
        # need to include the status of the system,  the number of messages received and osc input address/output address with ports
        message = { "message": self.status.name, 
                   "timestamp": time.time() , 
                   "data": {"osc_input_address":self.input_osc_address,"osc_input_port":self.osc_port,"osc_input_topic":self.osc_input_topic,"osc_output_address":self.output_osc_address,"osc_output_port":self.osc_port,"osc_output_topic":self.osc_output_topic,"message_counter":self.msg_counter},
                   "message_type": "status"}

        return message

    # process the websocket message function 
    def process_websocket_message(self, message):
        # print the message first 
        print(message)
        # parse the message in json format
        message = json.loads(message)
        # check the message type, check exist 
        if "message_type" in message:
            # check if the message type exist
            if ("message" in message):
                # check if the message in the supported lit
                if (message["message_type"] in ["command","status"]):
                    if (message["message_type"] =="command"):
                        # print out the command
                        print(message["message"])
                        # treat it accordingly 
                        if (message["message"]=="/command/train/start"):
                            # start training
                            if self.status == SystemStatus.STANDBY:
                                print("Start training")
                                # update the status
                                self.status = SystemStatus.TRAINING
                                self.simple_send_websocket_message("start_training",message_type="notification")
                                self.start_sampling = True
                                # signal to receive training data
                                # check if it is already training
                                if not self.training:
                                    self.training = True
                                    self.temp_buffer = []
                                    self.start_sampling = False
                            else:
                                print("System is not in standby mode")
                                self.simple_send_websocket_message("System is not in standby mode",message_type="error")

                        elif (message["message"]=="/command/train/add"):
                            # add training data
                            print("Add training data")
                            # check whether it is training
                            if self.status == SystemStatus.TRAINING:
                                # check whether the message contains data
                                if "data" in message:
                                    # check the data array size whether it is the same as the output number
                                    print(len(message["data"]))

                                    if len(message["data"]) == self.output_number:
                                        # add the data to the temp buffer
                                        self.trainning_data_x.append(self.past_data)
                                        self.trainning_data_y.append(message["data"])
                                        # construct a json file combine together with self.past_data and message["data"]
                                        data = {"data":self.past_data.getBuffer().tolist(),"label":message["data"]}
                                        self.simple_send_websocket_message("Added a new training point",data,message_type="notification")

                                    else:
                                        print("Data size is not the same as the output number")
                                        self.simple_send_websocket_message("Data size is not the same as the output number",message_type="error")
                                        
                                    # add the data to the temp buffer
                        elif (message["message"]=="/command/train/stop"):
                            # stop training
                            print("Stop training")
                            self.start_sampling = False
                        elif (message["message"]=="/command/model/save"):
                            # save the model
                            self.save_model("model.joblib")
                            print ("Model saved")

                        elif (message["message"]=="/command/model/load"):
                            # load the model
                            self.model = load("model.joblib")
                            print ("Model loaded")
                        elif (message["message"]=="/command/system/start"):
                            # start the osc server
                            self.initialize_osc_server()
                            print ("OSC started")
                            # print the port 
                            print(self.construct_status_json())
                            # signal to the websocket that the system is started with the constructed json message
                            #self.send_websocket_message(self.construct_status_json())
                            self.simple_send_websocket_message(self.construct_status_json())
                else:
                        print("Unknown command")
                        self.simple_send_websocket_message("Unknown command",message_type="error")
            else:
                        print("Unknown command")
                        self.simple_send_websocket_message("Unknown command",message_type="error")

    def simple_send_websocket_message(self, message, data=[],message_type="status"):
                    asyncio.run_coroutine_threadsafe(self.send_websocket_message(message,data,message_type), self.loop)


    def predict(self, data):
        # Implement your prediction function here
        return self.model.predict(data)

    def communicate(self, message):
        self.client.send_message("/prediction", message,'status')
        

    def construct_websocket_message(self, message, data=[], message_type="status"):
        # Construct a WebSocket message in JSON format
        print(data)
        message = { "message_type": message_type,"message": message , "timestamp": time.time() , "data": data}
        return json.dumps(message)


    async def send_websocket_message(self, message,data=[],message_type="status"):
        
        # print the message first
        print(message_type)
        if self.websocket:
            # print the websocket is started
            print("Websocket is started, Ready to send message")
            if (message_type =="status"):
                await self.websocket.send(self.construct_websocket_message(message,data,message_type))
            else:
                await self.websocket.send(self.construct_websocket_message(message,data,message_type))
            print(f"> {message}")
        else:
            print("No active WebSocket connection")

    def save_model(self, filename):
        dump(self.model, filename)

def main():
    # Create MLProcessing object with specified OSC input, output, ports and WebSocket port
    processor = MLProcessing(input_osc_address='0.0.0.0', 
                             output_osc_address='localhost',  # replace with your target address
                             osc_input_topic='/gyrosc/ok/gyro',
                             osc_output_topic='/prediction',
                             osc_port=5005, 
                             output_number=2,
                             websocket_port=5000)

    

    # Start listening for OSC messages and WebSocket commands
    processor.listen()


if __name__ == '__main__':
    main()
