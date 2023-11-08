from pythonosc import dispatcher
from pythonosc import osc_server

import numpy as np

def print_osc_message(unused_addr, *args):
    # put the argements into a numpy array
    data = np.array(args)
    print("From {}: Received message: {}".format(unused_addr, args))
    print(data)

def print_all_messages(unused_addr, *args):
    print("From {}: Received message: {}".format(unused_addr, args))

dispatcher = dispatcher.Dispatcher()
#dispatcher.set_default_handler(print_all_messages)

dispatcher.map("/prediction", print_osc_message)

server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", 6000), dispatcher)
print("Serving on {}".format(server.server_address))
server.serve_forever()