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
from threading import Thread
import pandas as pd

class SystemStatus(Enum):
    STANDBY = auto()
    PREDICTING = auto()
    TRAINING = auto()
    STOPPED = auto()

class MODEL_LIST(Enum):
    KNN = auto()
    DNN = auto()
    LSTM = auto()

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
    def __init__(self, input_osc_address, output_osc_address,osc_input_topic,osc_output_topic, osc_port, output_number,websocket_port,buffer_size=5):
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
        self.websocket_loop = None


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


    def start_websocket_server(self):
        self.websocket_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.websocket_loop)
        self.websocket_loop.run_until_complete(websockets.serve(self.websocket_handler, "localhost", self.websocket_port))

        try:
            self.websocket_loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            print("Closing asyncio loop.")
            self.websocket_loop.close()


    def listen(self):
        self.osc_server = BlockingOSCUDPServer((self.input_osc_address, self.osc_port), self.dispatcher)
        print(f"Listening for OSC on {self.osc_server.server_address}")

        # Start WebSocket server in a separate thread
        t = Thread(target=self.start_websocket_server)
        t.start()

        main_loop = asyncio.get_event_loop()
        main_loop.create_task(self.send_regular_status_report())

        # run the loop forever, in the background
        try:
            main_loop.run_forever()
        except KeyboardInterrupt:
            pass
        finally:
            print("Closing asyncio loop.")
            main_loop.close()


        self.osc_server.shutdown()
        self.osc_thread.join()



    async def send_regular_status_report(self):
        while True:
            # send the regular status report
            print("Sending regular status report")
            ## send the regular status report when the status is not in standby mode
            if self.status != SystemStatus.STOPPED:
                # send the regular status report
                self.simple_send_websocket_message(self.construct_regular_status_report())
            # sleep for 5 seconds
            time.sleep(5)


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
        # counter +1 
        self.msg_counter +=1

        self.past_data.add(data)
        #self.maintain_buffer(data)
        #iltered_data = self.filter_data(data)

        # if it is predicting, then predict the data
        if self.status == SystemStatus.PREDICTING:
            prediction = self.predict([data])
            # send the data to the websocket
            self.simple_send_websocket_message("Predicting",prediction,message_type="prediction")

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

    def train(self, model_type="KNN"):
        # Implement your training function here
        # start training
        print(self.trainning_data_x,self.trainning_data_y)
        df_x = pd.DataFrame(self.trainning_data_x)
        df_y = pd.DataFrame(self.trainning_data_y)
        # current df_x contains an array of an array, need to iterate all the elements of it and flatten and convert it to a dataframe
        #df_x = pd.DataFrame([item for sublist in self.trainning_data_x for item in sublist])
        # Create a DataFrame
        data =self.trainning_data_x

        # Flatten and rename the series
        frames = []
        for i, arr in enumerate(data):
            df = pd.DataFrame(arr)
            s = df.stack().reset_index()
            s.index = ['x_'  + str(x[0]) + '_' + str(x[1]) for x in s[['level_0', 'level_1']].values]
            frames.append(s[0].to_frame().T)

        # Concatenate all DataFrame rows into a single DataFrame
        df_flat = pd.concat(frames, ignore_index=True)

        # Print the result
        df_x = df_flat

        

        df_x.to_csv("trainning_data_x.csv")
        df_y.to_csv("trainning_data_y.csv")
        # check the model type
        if model_type == "KNN":
            self.model = KNeighborsClassifier(n_neighbors=3)
            # start training using the training data x and y
            # singal to the websocket that training is started 
            # iterate through the training data x, and sum up the data

            # Your 3D array
            data = self.trainning_data_x

            # Initialize an empty list
            appended_data = []

            # Loop through each subarray and append the first inner list to 'appended_data'
            for subarray in data:
                appended_data.append(subarray[-1])

            self.model.fit(appended_data, self.trainning_data_y)
            # combine the training data x and y into panda dataframe， with x,y

            # signal to the websocket that training is done
            self.simple_send_websocket_message("Training is done",message_type="notification")
            self.is_training_complete = True

    def construct_status_json(self):
        # need to include the status of the system,  the number of messages received and osc input address/output address with ports
        message = { "message": self.status.name, 
                   "timestamp": time.time() , 
                   "data": {"osc_input_address":self.input_osc_address,"osc_input_port":self.osc_port,"osc_input_topic":self.osc_input_topic,"osc_output_address":self.output_osc_address,"osc_output_port":self.osc_port,"osc_output_topic":self.osc_output_topic,"message_counter":self.msg_counter},
                   "message_type": "status"}

        return message
    
    def construct_regular_status_report(self):
        # report the existing message, the collected sample sizes
        message = { "message_type": "status_report" , "timestamp": time.time() , "data": {"message_counter":self.msg_counter,"sample_size":len(self.trainning_data_x)}}
        return message
    
    def get_all_training_data(self):
        temp_msg = {"message_type": "training_data" , "timestamp": time.time() , "data": {"x":self.trainning_data_x,"y":self.trainning_data_y}}
        

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

                                    # check whether there are enough data in the past buffer, if not, give error to the websocket
                                    if self.past_data.isEmpty():
                                        print("Not enough data in the past buffer")
                                        self.simple_send_websocket_message("Not enough data in the past buffer",message_type="error")
                                        return
                                        

                                    
                                    if len(message["data"]) == self.output_number:
                                        # add the data to the temp buffer
                                        self.trainning_data_x.append(self.past_data.getBuffer().tolist())
                                        self.trainning_data_y.append(message["data"])
                                        #print (self.trainning_data_x,self.trainning_data_y)
                                        # construct a json file combine together with self.past_data and message["data"]
                                        data = {"data":self.past_data.getBuffer().tolist(),"label":message["data"]}
                                        self.simple_send_websocket_message("Added a new training point",data,message_type="notification")

                                    else:
                                        print("Data size is not the same as the output number")
                                        self.simple_send_websocket_message("Data size is not the same as the output number",message_type="error")
                                        
                                    # add the data to the temp buffer
                                else:
                                    print("No data in the message")
                                    self.simple_send_websocket_message("No data in the message",message_type="error")
                            else:
                                print("System is not in training mode")
                                self.simple_send_websocket_message("System is not in training mode",message_type="error")
                        elif (message["message"]=="/command/train/finish"):
                            self.train()
                            # finish training
                            print("Finish training")
                            # update the status
                            self.status = SystemStatus.PREDICTING

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
                    asyncio.run_coroutine_threadsafe(self.send_websocket_message(message,data,message_type), self.websocket_loop)


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
            #print("Websocket is started, Ready to send message")
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
                             output_number=1,
                             websocket_port=5000)

    

    # Start listening for OSC messages and WebSocket commands
    processor.listen()


if __name__ == '__main__':
    main()
