import time
import meshtastic
import meshtastic.tcp_interface
from pubsub import pub

seperator="\n ---------------\n"

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

def messageReplyTo(interface, message):
    sender = message["fromId"]
    destination = message["toId"]

    print(f"Recevied message from: {sender} to: {destination}")

    reply = "Ignore Please"
    reply = reply + "\nYour message:" + str(message["decoded"]["payload"])[:10] + "..."
    if "pkiEncrypted" in message:
        reply = reply + "\npkiEncrypted:" + str(message["pkiEncrypted"])
    if "wantAck" in message:
        reply = reply + "\nwantAck:" + str(message["wantAck"])
    if "rxSnr" in message:
        reply = reply + "\nrxSnr:" + str(message["rxSnr"])
    if "rxRssi" in message:
        reply = reply + "\nrxRssi:" + str(message["rxRssi"])
    if "hopLimit" in message:
        reply = reply + "\nhopLimit:" + str(message["hopLimit"])
    if "hopStart" in message:
        reply = reply + "\nhopStart:" + str(message["hopStart"])

    if sender in knownNodes:
        print(f"Sending reply back to {sender}")
        interface.sendText(reply, sender)
    else:
        print(f"Not sending reply back to {sender}")
#        interface.sendText(reply, sender)


def onReceive(packet, interface): # called when a packet arrives
    print(f"{seperator}Received packet: {packet}")

def onConnection(interface, topic=pub.AUTO_TOPIC): # called when we (re)connect to the radio
    # defaults to broadcast, specify a destination ID if you wish
    #interface.sendText("hello mesh")

    print(f"{seperator}Got a connection to the radio")
    if interface.nodes:
        for n in interface.nodes.values():
            if n["num"] == interface.myInfo.my_node_num:
                print(n["user"]["hwModel"])
                break

def onNodeUpdated(node, interface):
#def onNodeUpdated(node, interface):
    print(f"{seperator}Node updated")
    print(f"{node}")
    print(f'User ID = {node["user"]["id"]}')

   # if it's one of the known nodes, send it a message
    if node["user"]["id"] in knownNodes:
        print(f'Sending direct message to {node["user"]["id"]}')
        interface.sendText("Test - found my own node!!!", node["user"]["id"])


def onReceiveText(packet, interface):
    print(f"{seperator}Received Text: {packet}")
    messageReplyTo(interface, packet)


# main code

# Example usage
knownNodes = read_file_to_array("nodes_to_interact_with.txt")

# Print the array
print(knownNodes)

#pub.subscribe(onReceive, "meshtastic.receive")
pub.subscribe(onConnection, "meshtastic.connection.established")
pub.subscribe(onNodeUpdated, "meshtastic.node.updated")
pub.subscribe(onReceiveText, "meshtastic.receive.text")

interface = meshtastic.tcp_interface.TCPInterface(hostname='localhost')
while True:
    time.sleep(1000)
interface.close()
