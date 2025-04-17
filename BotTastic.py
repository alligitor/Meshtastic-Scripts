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


#global variables

# dictionary for holding all the nodes we get via onNodeUpdated
dictAllNodes = {}

seperator="\n ---------------\n"

#common messages people send to test their connection
connection_test_requests = ["testing", "test", "radio check", "antenna check"]

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

# Function to read the json file and store
def read_json_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data
    except FileNotFoundError:
        print(f"File {file_path} not found.")
        return []
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
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

    #dig up the node info from the interface object
    senderNode = getNodeInfo(interface, sender)
    #if (senderNode != None):
    #    print({senderNode})

    #use the trim function to remove extra characters resulging from it being a binary coded string
    message_payload = TrimDecodedMessage(str(message["decoded"]["payload"].decode("UTF-8")))

    #print(f"Recevied message from: {sender} to: {destination}")

    send_reply = False
    message_type = "none"

    #generic creator of replies for messages
    if (message_payload.lower() in connection_test_requests):
        #someone reqeusted a test
        reply = "@" + sender
        reply = reply + "\nAck from SW 01803"
        if "pkiEncrypted" in message:
            reply = reply + "\npkiEncrypted:" + str(message["pkiEncrypted"])
        if "wantAck" in message:
            reply = reply + "\nwantAck:" + str(message["wantAck"])
        if "rxSnr" in message:
            reply = reply + "\nrxSnr:" + str(message["rxSnr"])
        if "rxRssi" in message:
            reply = reply + "\nrxRssi:" + str(message["rxRssi"])
        if "hopLimit" in message and "hopStart" in message:
            reply = reply + "\nhopLimit:" + str(message["hopLimit"])
            reply = reply + "\nhopStart:" + str(message["hopStart"])
            hopCount = message["hopStart"] - message["hopLimit"]
            reply = reply + "\nHops:" + str(hopCount)
        message_type = "connection_test"
    elif (message_payload.lower() == "help"):
        reply = "@" + sender + "\navailable commands"
        reply = reply + "\nhelp"
        reply = reply + "\ntest"
        reply = reply + "\necho"
        reply = reply + "\nping"
        reply = reply + "\ndistance"
        message_type = "help"
    elif (message_payload.lower() == "echo"):
        #someone reqeusted a echo
        reply = "@" + sender + "\nRXed your message"
        reply = reply + "\nYour message:" + message_payload
        message_type = "echo"
    elif (message_payload.lower() == "distance"):
        #someone reqeusted a distance calculation
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
                reply = "@" + sender + f"\nWe are {distance} km apart"
            else:
                reply = "@" + sender + "\nyou don't have position info"
        else:
            reply = "@" + sender + "\nSorry, don't know about your node"

        message_type = "distance"
    elif (message_payload.lower() == "ping"):
        #someone reqeusted a distance calculation
        reply = "@" + sender + "\npong"
        message_type = "ping"
    else:
        #pass to SplotchPlus
        reply = SplotchPlusSendMessage(message_payload)
        message_type = "splotchplus"
 
    print("---->")
    print(f"Sender: {sender} to Destination: {destination}")
    print(f"\nInitial: {message_payload}\nReply: {reply}")

    if destination == "^all":
        # message was broadcast to all
        knownNode = findKnownNode(sender)

        if knownNode != None:
            print(f"B/C Message from known node {sender}.")
            if message_type in ["connection_test", "help", "echo", "ping"]:
                send_reply = True
        else:
            print(f"B/C Message from unknown node {sender}")
            #in public channel limit replies to a few things such as connection_test, help, echo
            if message_type in ["connection_test", "help", "echo", "ping"]:
                send_reply = True
    else:
        #message was to us directly
        knownNode = findKnownNode(sender)
        if knownNode != None:
            print(f"D/M Message from known node {sender}.")
            send_reply = True
            destination = sender
        else:
            print(f"D/M Message from unknown node {sender}")
            send_reply = True
            destination = sender

    if send_reply == True:
        print(f"Sending message to {destination}")
        if destination == "^all":
            interface.sendText(reply)
        else:
            interface.sendText(reply, destination)
    else:
        print(f"Not Sending message to {destination}")

    #final marker for current message that was processed
    print("<----")

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

    #add to global node dictionary
    dictAllNodes.update( {node["user"]["id"] : node})

    # if it's one of the known nodes, send it a message
    nodeId = node["user"]["id"]

    knownNode = findKnownNode(nodeId)
    if (knownNode != None):
        match knownNode.get('action'):
            case "Message":
                print(f"Sending >{knownNode.get('message')}< to >{nodeId}<")
                interface.sendText(knownNode.get('message'), nodeId)
            case _:
                None


def onReceiveText(packet, interface):
    #print(f"{seperator}Received Text: {packet}")
    #put a marker here so it's easier for us to see when a new text packet has come in
    print(">------------------------------------<")
    try:
        messageReplyTo(interface, packet)
    except:
        exit(0)


############################
# main code

#code for just testing splotch subprocess code
#SplotchPlusSendMessage("I don't like Windows")
#exit(1)


# Example usage
#knownNodes = read_file_to_array("nodes_to_interact_with.txt")
knownNodes = read_json_file("nodes_to_interact_with.json")

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

    while True:
        time.sleep(2)

        #keep an eye on the socket to see if it closed
        if isSocketConnected(interface.socket):
            None
            #print("Socket is connected")
        else:
            print("Socket is disconnected")
            interface.close()
            exit(4)

except :
    print("meshtastic.tcp_interface.TCPInterface failed")

