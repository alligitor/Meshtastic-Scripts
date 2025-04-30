import time
import meshtastic
import meshtastic.tcp_interface
import subprocess
import time
import math
from pubsub import pub
import json
import socket
import select
from meshtastic.protobuf import mesh_pb2, portnums_pb2, telemetry_pb2
import random
from datetime import datetime
import threading
import base64


#global variables

# dictionary for holding all the nodes we get via onNodeUpdated
dictAllNodes = {}
dictAllNodesLock = threading.Lock()

#list of known Nodes
knownNodes = {}

#file name for storing nodes in a json file
nodeStorageFilename = "/tmp/allNodes.json"

seperator="\n ---------------\n"

#common messages people send to test their connection
connection_test_requests = ["testing", "test", "radio check", "antenna check"]

#function to save a string to a file. 
def logMessageToFile(file_name, text_to_append):
    try:
        with open(file_name, 'a') as file:
            file.write(text_to_append + '\n')
    except Exception as e:
	#ignore errors
        None

# routine to see if a socket is open or close
def isSocketConnected(sock):
    r, _, _ = select.select([sock], [], [], 0)
    if r:
        data = sock.recv(1, socket.MSG_PEEK)
        if not data:
            return False
    return True

# Function to calculate distance between two GPS points using the Haversine formula
def haversine(lat1, lon1, lat2, lon2):
    # Radius of Earth in kilometers (use 3958.8 for miles)
    R = 6371.0

    # Convert latitude and longitude from degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Differences in coordinates
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    # Haversine formula
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # Calculate the distance
    distance = R * c

    return distance

def TrimDecodedMessage(user_input):

    #print(f"user_input before: -->{user_input}<--")

    #replace a bunch of characters to old school
    #so splotch plus can handle it
    #there might be other stuff here that needs to be replaced
    user_input = user_input.replace('’', "'").replace('‘', "'")
    user_input = user_input.replace('“', '"').replace('”', '"')

    #user_input = user_input.decode("utf-8")
    #print(f"user_input after decoding: -->{user_input}<--")

    #user input is comming in decode, so won't have b'   and '
    #remove the first two characters
    #user_input = user_input[2:]

    #remove any white space on left side
    user_input = user_input.lstrip()
    #print(f"user_input after left trim: -->{user_input}<--")

    # remove the last character
    #user_input = user_input[:-1]
    #remove any white space on right side
    user_input = user_input.rstrip()
    #print(f"user_input after right trim: -->{user_input}<--")

    return (user_input)

def SplotchPlusSendMessage(user_input):
    # Start a subprocess to run the Python interactive input() function
    process = subprocess.Popen(
        ['./chat'],
        stdout=subprocess.PIPE,  # Capture the standard output
        stdin=subprocess.PIPE,   # Allow us to send input to the process
        stderr=subprocess.PIPE,  # Capture any error output
        text=True  # Work with strings (not bytes)
    )

    #print(f"Waiting 1 second for splotchPlus to start up")
    #time.sleep(1)

    #for dealing with splotch limit the string to 50 charactors.  Not sure what SplotchPlus can do with more anyways
    user_input = user_input[:50]

    #convert to lower case since splotch is case sensative
    user_input = user_input.lower()

    # make sure there is only one string in there with a \n
    # if there are no \n, append one

    # Find the index of the first newline character
    position_of_newline = user_input.find('\n')

    # Extract the substring up to the first newline (if newline exists)
    if position_of_newline != -1:
        #print(f"Extracted string up to the first '\\n': {extracted_string}")
        extracted_string = user_input[:position_of_newline+1]
    else:
        #print("No newline character '\\n' found in the string, adding one")
        user_input = user_input + "\n"


    #print(f"Writing message to SplotchPlus -->{user_input}<--")
    process.stdin.write(user_input)
    process.stdin.flush()
    process.stdin.write(user_input)
    process.stdin.flush()


    #print(f"Reading line from SplotchPlus")
    stdout = process.stdout.readline()

    # Output the response from the process
    #print("Standard Output:")
    #print(stdout)

    process.terminate()
    process.wait()

    # Print the final return code (0 means successful execution)
    #print(f"Return Code: {process.returncode}")

    return stdout

def saveDataToJSONfile(filename, data):
    #currently, the dump function causes an error
    #saveDataToJSONfile Type <class 'meshtastic.protobuf.mesh_pb2.MeshPacket'> not serializable
    #disabling this until we figure it out
    #return

    def default_serializer(obj):
        if isinstance(obj, bytes):
            return {'__bytes__': True, 'data': base64.b64encode(obj).decode('utf-8')}
        else:
            #if there's an error, just put some words, we'll debug later
            return {'__bytes__': True, 'data': "^V^V^V^V^V^V^V^V^V^"}
        raise TypeError(f"Type {type(obj)} not serializable")
    try:
        # Save to file
        with open(filename, 'w') as f:
            json.dump(data, f, default=default_serializer, indent=2)
    except Exception as e:
        print(f"Error in saveDataToJSONfile {e}")

def loadDataFromJSONFile(filename):
    def object_hook(obj):
        if '__bytes__' in obj:
            if obj['data'] == "^V^V^V^V^V^V^V^V^V^":
                return obj
            else:
                return base64.b64decode(obj['data'].encode('utf-8'))
        return obj

    try:
        with open(filename, 'r') as f:
            data = json.load(f, object_hook=object_hook)
            return data
    except FileNotFoundError:
        print(f"File {file_path} not found.")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return None

# Function to read the file and store each line in an array
def read_file_to_array(file_path):
    lines = []  # Initialize an empty list
    try:
        with open(file_path, 'r') as file:
            # Read each line and append it to the list
            for line in file:
                lines.append(line.strip())  # Using strip() to remove any leading/trailing whitespace
        return lines
    except FileNotFoundError:
        print(f"Error: The file at {file_path} was not found.")
        return []
    except Exception as e:
        print(f"An error occurred: {e}")
        return []

def findKnownNode(nodeId):
    for node in knownNodes:
        if (nodeId == node.get('Id')):
            return node
    return None

def getNodeInfo(interface, target_node_id):

    #default return value
    returnedNode = None

    #for node in interface.nodes: #.values():  # Access nodes from the interface
        #print(f"Node Information -->{node}<--")

        # if node.id == target_node_id:
        #     print(f"Node Found: {node.id}")
        #     print(f"Node Name: {node.get('name', 'Unnamed')}")
        #     print(f"Node Lat: {node.get('lat', 'N/A')}")
        #     print(f"Node Lon: {node.get('lon', 'N/A')}")
        #     print(f"Node Last Seen: {node.get('lastHeard', 'N/A')}")
        #     returnedNode = node
        #     break

    return returnedNode

def messageReplyTo(interface, message):
    sender = message["fromId"]
    destination = message["toId"]

    #print my node information to see what it looks like
    myNodeInfo = interface.getMyNodeInfo()

    myNodeId = myNodeInfo['user']['id']
    if (myNodeId.startswith("!")):
        # remove the !
        myNodeId = myNodeId[1:]
    #at this point, myNodeId hould have 8 characters.  double check
    if (len(myNodeId) != 8):
        #set it to some junk if not equal to 8
        myNodeId = "xxxxyyyy"

    #create a bunch of aliases that I would assume is me
    myNodeAliases = []
    myNodeAliases.append(myNodeId[-4:]) #last 4 of the id
    myNodeAliases.append("@" + myNodeId[-4:]) #last 4 of the id, starting with @
    myNodeAliases.append(myNodeId) #all 8 digits
    myNodeAliases.append("@" + myNodeId) # @ followed by all 8 digits



    #dig up the node info from the interface object
    senderNode = getNodeInfo(interface, sender)
    #if (senderNode != None):
    #    print({senderNode})

    #use the trim function to remove extra characters resulting from it being a binary coded string
    try:
        #sometimes decode fails
        message_payload = TrimDecodedMessage(str(message["decoded"]["payload"].decode("UTF-8")))
    except:
        print(f"Message causing decode exception: {str(message['decoded']['payload'])}")
        message_payload = TrimDecodedMessage(str(message["decoded"]["payload"]))

    #print(f"Recevied message from: {sender} to: {destination}")

    send_reply = False
    message_type = "none"

    #generic creator of replies for messages
    if (message_payload.lower() in connection_test_requests):
        #someone reqeusted a test
        reply = "Ack from SW 01803"
        if "pkiEncrypted" in message:
            reply = reply + "\npkiEncrypted:" + str(message["pkiEncrypted"])
        if "wantAck" in message:
            reply = reply + "wantAck:" + str(message["wantAck"])
        if "rxSnr" in message:
            reply = reply + "rxSnr:" + str(message["rxSnr"])
        if "rxRssi" in message:
            reply = reply + "rxRssi:" + str(message["rxRssi"])
        if "hopLimit" in message and "hopStart" in message:
            reply = reply + "hopLimit:" + str(message["hopLimit"])
            reply = reply + "\nhopStart:" + str(message["hopStart"])
            hopCount = message["hopStart"] - message["hopLimit"]
            reply = reply + "\nHops:" + str(hopCount)
        message_type = "connection_test"
    elif (message_payload.lower() == "debug"):
        #print(f"{dictAllNodes}")
        reply = "known nodes = " + str(len(dictAllNodes))
        with dictAllNodesLock:
            saveDataToJSONfile(nodeStorageFilename, dictAllNodes)
        message_type = "debug"
    elif (message_payload.lower() == "help"):
        reply = "available commands"
        reply = reply + "\nhelp"
        reply = reply + "\ntest"
        reply = reply + "\necho"
        reply = reply + "\nping"
        reply = reply + "\ndistance"
        message_type = "help"
    elif (message_payload.lower()[:len("echo")] == "echo"):
        #someone reqeusted a echo
        reply = "echoing: "
        reply = reply + message_payload[len("echo"):]
        message_type = "echo"
    elif (message_payload.lower() == "distance"):
        #someone reqeusted a distance calculation
        with dictAllNodesLock:
            if sender in dictAllNodes:
                if "position" in dictAllNodes[sender]:
                    senderLatitude  = dictAllNodes[sender]["position"]["latitude"]
                    senderLongitute = dictAllNodes[sender]["position"]["longitude"]

                    myNodeInfo = interface.getMyNodeInfo()
                    myLatitude  = myNodeInfo["position"]["latitude"]
                    myLongitute = myNodeInfo["position"]["longitude"]

                    # print(f"My     Position: {myLatitude}, {myLongitute}")
                    # print(f"Sender Position: {senderLatitude}, {senderLongitute}")
                    distance = haversine(senderLatitude, senderLongitute, myLatitude, myLongitute)
                    reply = f"We are {distance} km apart"
                else:
                    reply = "you don't have position info"
            else:
                reply = "Sorry, don't know about your node"

        message_type = "distance"
    elif (message_payload.lower()[:len("ping")] == "ping"):
        #someone reqeusted a distance calculation
        reply = "pong"
        message_type = "ping"
    else:
        #check to see if the begining of the message was an indication it was destined to us directly
        #people use this in the public channel
        for alias in myNodeAliases:
           if (message_payload.lower()[:len(alias)] == alias):
               #remove the alias from begining of the message
               message_payload = message_payload[len(alias):]
               message_type = "splotchplus_directed"

        #pass to SplotchPlus
        reply = SplotchPlusSendMessage(message_payload)

        if (message_type != "splotchplus_directed"):
            message_type = "splotchplus"

    #create the message that goes to the console about the message
    conversation_log = ""
    conversation_log += "---->\n"
    #the following code modifies destination, keep a copy of the original one
    original_destination = destination

    if destination == "^all":
        # message was broadcast to all
        knownNode = findKnownNode(sender)

        if knownNode != None:
            conversation_log += f"B/C Message from known node {sender}.\n"
            if message_type in ["connection_test", "help", "echo", "ping", "splotchplus_directed"]:
                send_reply = True
        else:
            conversation_log += f"B/C Message from unknown node {sender}\n"
            #in public channel limit replies to a few things such as connection_test, help, echo
            if message_type in ["connection_test", "help", "echo", "ping", "splotchplus_directed"]:
                send_reply = True
    else:
        #message was to us directly
        knownNode = findKnownNode(sender)
        if knownNode != None:
            conversation_log += f"D/M Message from known node {sender}.\n"
            send_reply = True
            destination = sender
        else:
            conversation_log += f"D/M Message from unknown node {sender}\n"
            send_reply = True
            destination = sender

    #prepend @sender to the begining of messages if destination is public channel
    if (destination == "^all"):
        reply = "@" + sender + "\n" + reply

    #build a string of the message and reply to log
    conversation_log += f"       sent to destination: {original_destination}\n"
    conversation_log += f"\nInitial: {message_payload}\nReply: {reply}\n"

    if send_reply == True:
        conversation_log += f"Sending message to {destination}\n"
        if destination == "^all":
            interface.sendText(reply)
        else:
            interface.sendText(reply, destination)
    else:
        conversation_log += f"Not Sending message to {destination}\n"

    #final marker for current message that was processed
    conversation_log += "<----\n"

    # print the mssage to screen and also log it
    print(conversation_log)
    logMessageToFile("/tmp/splotchplus_msg_log.txt", conversation_log)

def onReceive(packet, interface): # called when a packet arrives
    #print(f"{seperator}Received packet: {packet}")
    # don't do anything on packet reception
    return

def onConnectionEstablished(interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
    print(f">>-- Interface --<<")
    print(f"{interface.socket}")

    print(f"{seperator}Got a connection to the radio")
    if interface.nodes:
        for n in interface.nodes.values():
            if n["num"] == interface.myInfo.my_node_num:
                print("My node ID: " + n["user"]["id"])
                print(f"{seperator}")
                break

def onConnectionLost(interface):
    print(f"{seperator}Lost connection to the radio")

def onNodeUpdated(node, interface):
    #print(f"{seperator}Node updated")
    #print(f"{node}")
    #print(f'User ID = {node["user"]["id"]}')

    nodeId = node["user"]["id"]

    #add to global node dictionary
    with dictAllNodesLock:
        dictAllNodes.update( {nodeId : node})

    # if it's one of the known nodes, send it a message
    knownNode = findKnownNode(nodeId)
    if (knownNode != None):
        match knownNode.get('action'):
            case "Message":
                print(f"Sending >{knownNode.get('message')}< to >{nodeId}<")
                interface.sendText(knownNode.get('message'), nodeId)
            case _:
                None

    #add a new dictionary to the node for storing my data
    with dictAllNodesLock:
        if dictAllNodes[nodeId].get("BotTasticData") ==  None:
            dictAllNodes[nodeId]["BotTasticData"] = {}

        saveDataToJSONfile(nodeStorageFilename, dictAllNodes)

def onReceiveText(packet, interface):
    #print(f"{seperator}Received Text: {packet}")
    #put a marker here so it's easier for us to see when a new text packet has come in
    print(">------------------------------------<")
    try:
        messageReplyTo(interface, packet)
    except:
        exit(0)

def onReceiveDataPort_TELEMETRY_APP(packet):
    #print(">------------------------------------<")
    #print(f"    {packet}")

    fromNode = packet['fromId']
    timeStamp = datetime.now()

    result = timeStamp.strftime("%Y-%m-%d %H:%M:%S")
    result = result + " - "

    if packet['decoded']['portnum'] == "TELEMETRY_APP":

        result += f"Received telementry update from {fromNode}"

        #update our internal structure when we received the response
        with dictAllNodesLock:
            dictAllNodes[fromNode]["BotTasticData"]["TelemetryTimeReceived"] = timeStamp.isoformat()

            logMessageToFile("/tmp/telemetry_result.txt", result)

            saveDataToJSONfile(nodeStorageFilename, dictAllNodes)
    else:
        result += f"Received unexpected port {packet['decoded']['portnum']}"

def sendTelementryToRandomNode(interface):
    # pick another node at random and send a message
    #print("sendTelementryToRandomNode")
    try:
        if interface.nodesByNum is not None:
            node = interface.nodesByNum.get(interface.localNode.nodeNum)
            if node is not None:
                metrics = node.get("deviceMetrics")
                if metrics:
                    r = telemetry_pb2.Telemetry()

                    batteryLevel = metrics.get("batteryLevel")
                    if batteryLevel is not None:
                        r.device_metrics.battery_level = batteryLevel
                    if False:
                        voltage = metrics.get("voltage")
                        if voltage is not None:
                            r.device_metrics.voltage = voltage
                        channel_utilization = metrics.get("channelUtilization")
                        if channel_utilization is not None:
                            r.device_metrics.channel_utilization = channel_utilization
                        air_util_tx = metrics.get("airUtilTx")
                        if air_util_tx is not None:
                            r.device_metrics.air_util_tx = air_util_tx
                        uptime_seconds = metrics.get("uptimeSeconds")
                        if uptime_seconds is not None:
                            r.device_metrics.uptime_seconds = uptime_seconds
     
                    if len(dictAllNodes) > 0:
                        with dictAllNodesLock:
                            dest = random.choice(list(dictAllNodes))
                            print(f"Sending Telemetry to {dest}")

                            #record when we sent the request
                            #dictAllNodes[dest]["BotTasticData"]["TelemetryTimeSent"] = datetime.now()
                            dictAllNodes[dest]["BotTasticData"]["TelemetryTimeSent"] = datetime.now().isoformat()
                            saveDataToJSONfile(nodeStorageFilename, dictAllNodes)

                        interface.sendData(r,
                                    destinationId=dest,
                                    portNum=portnums_pb2.PortNum.TELEMETRY_APP,
                                    wantResponse=True,
                                    onResponse=onReceiveDataPort_TELEMETRY_APP,
                                    channelIndex=0,
                                    )
    except e:
        print("Error {e}")

def main():
    ############################
    # main code

    #code for just testing splotch subprocess code
    #SplotchPlusSendMessage("I don't like Windows")
    #exit(1)

    global knownNodes
    knownNodes = loadDataFromJSONFile("nodes_to_interact_with.json")

    global dictAllNodes
    dictAllNodes = loadDataFromJSONFile(nodeStorageFilename)
    if dictAllNodes == None:
        dictAllNodes = {}
    print(f'Loaded {len(dictAllNodes)} nodes from storage')


    # Print the array
    print(">------- Known Nodes --------<")
    print(knownNodes)
    print(">----------------------------<")

    #pub.subscribe(onReceive, "meshtastic.receive")
    pub.subscribe(onConnectionEstablished, "meshtastic.connection.established")
    pub.subscribe(onConnectionLost, "meshtastic.connection.lost")
    pub.subscribe(onNodeUpdated, "meshtastic.node.updated")
    pub.subscribe(onReceiveText, "meshtastic.receive.text")

    try:
        interface = meshtastic.tcp_interface.TCPInterface(hostname='localhost')

        start_time = time.time()
        
        while True:
            time.sleep(2)

            #keep an eye on the socket to see if it closed
            if isSocketConnected(interface.socket):
                None
                #While connected wake up eveyr 5 seconds and do something
                current_time = time.time()
                elapsed = current_time - start_time

                #send a message to a random node every 15 seconds
                #checks to see if any node responds
                if elapsed >= 120:
                    None
                    if True: #if statement for turning this code on / off
                        #print(f"{int(elapsed)} seconds have passed.")
                        start_time = time.time()

                        # pick another node at random and send a message
                        sendTelementryToRandomNode(interface)
            else:
                print("Socket is disconnected")
                interface.close()
                exit(4)

    except :
        print("meshtastic.tcp_interface.TCPInterface failed")

if __name__ == "__main__":
    main()
