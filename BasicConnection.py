import time
import meshtastic
import meshtastic.tcp_interface
import subprocess
import time
from pubsub import pub

seperator="\n ---------------\n"


def SplotchPlusSendMessage(user_input):
    # Start a subprocess to run the Python interactive input() function
    process = subprocess.Popen(
        ['./chat'],
        stdout=subprocess.PIPE,  # Capture the standard output
        stdin=subprocess.PIPE,   # Allow us to send input to the process
        stderr=subprocess.PIPE,  # Capture any error output
        text=True  # Work with strings (not bytes)
    )

    print(f"Waiting 1 second for splotchPlus to start up")
    time.sleep(1)

    print(f"user_input before any trim: {user_input}")

    #remove the first two characters
    user_input = user_input[2:]
    print(f"user_input after left trim: {user_input}")
    # remove the last character
    user_input = user_input[:-1]
    print(f"user_input after right trim: {user_input}")
    #user_input = "i like x"

    #now limit the string to 50 charactors.  Not sure what SplotchPlus can do with more anyways
    user_input = user_input[:50]

    #convert to lower case since splotch is case sensative
    user_input = user_input.lower()


    # make sure there is only one string in there with a \n
    # if there are no \n, append one

    # Find the index of the first newline character
    position_of_newline = user_input.find('\n')

    # Extract the substring up to the first newline (if newline exists)
    if position_of_newline != -1:
        extracted_string = user_input[:position+1]
        print(f"Extracted string up to the first '\\n': {extracted_string}")
    else:
        print("No newline character '\\n' found in the string, adding one")
        user_input = user_input + "\n"


    print(f"Writing message to SplotchPlus {user_input}")
    process.stdin.write(user_input)
    process.stdin.flush()
    process.stdin.write(user_input)
    process.stdin.flush()


    print(f"Reading line from SplotchPlus")
    stdout = process.stdout.readline()

    # Output the response from the process
    print("Standard Output:")
    print(stdout)

    process.terminate()
    process.wait()

    # Print the final return code (0 means successful execution)
    print(f"Return Code: {process.returncode}")

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

def messageReplyTo(interface, message):
    sender = message["fromId"]
    destination = message["toId"]

    message_payload = str(message["decoded"]["payload"])

    print(f"Recevied message from: {sender} to: {destination}")

    reply = "Ignore Please"
    reply = reply + "\nYour message:" + message_payload[:10] + "..."
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
        reply = SplotchPlusSendMessage(message_payload)
        print(f"Sending reply back to {sender}")
        interface.sendText(reply, sender)
    else:
        if destination != "^all":
            #message was to us directly
            print(f"DM message. Not sending reply back to {sender}")
        else:
            #messae was sent to all
            print(f"Broadcast message. Not sending reply back to {sender}")
#           interface.sendText(reply, sender)


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

#code for just testing splotch subprocess code
#SplotchPlusSendMessage("I don't like Windows")
#exit(1)


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
