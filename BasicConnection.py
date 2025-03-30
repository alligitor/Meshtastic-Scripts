import time
import meshtastic
import meshtastic.tcp_interface
import subprocess
import time
from pubsub import pub

seperator="\n ---------------\n"

#common messages people send to test their connection
connection_test_requests = ["testing", "test", "radio check", "antenna check"]

def TrimDecodedMessage(user_input):

    print(f"user_input before: -->{user_input}<--")

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
    print(f"user_input after left trim: -->{user_input}<--")

    # remove the last character
    #user_input = user_input[:-1]
    #remove any white space on right side
    user_input = user_input.rstrip()
    print(f"user_input after right trim: -->{user_input}<--")

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

    #use the trim function to remove extra characters resulging from it being a binary coded string
    message_payload = TrimDecodedMessage(str(message["decoded"]["payload"].decode("UTF-8")))

    print(f"Recevied message from: {sender} to: {destination}")

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
        if "hopLimit" in message:
            reply = reply + "\nhopLimit:" + str(message["hopLimit"])
        if "hopStart" in message:
            reply = reply + "\nhopStart:" + str(message["hopStart"])
        message_type = "connection_test"
    elif (message_payload.lower() == "help"):
        reply = "@" + sender + "\navailable commands"
        reply = reply + "\nhelp"
        reply = reply + "\ntest"
        reply = reply + "\necho"
        reply = reply + "\ndistance"
        message_type = "help"
    elif (message_payload.lower() == "echo"):
        #someone reqeusted a echo
        reply = "@" + sender + "\nRXed your message"
        reply = reply + "\nYour message:" + message_payload
        message_type = "echo"
    elif (message_payload.lower() == "distance"):
        #someone reqeusted a distance calculation
        reply = "@" + sender + "\ndistance not implemented"
        message_type = "distance"
    else:
        #pass to SplotchPlus
        reply = SplotchPlusSendMessage(message_payload)
        message_type = "splotchplus"
 
    print("---->")
    print(f"Sender: {sender}\nDestination: {destination}\nMessage: {message_payload}\nReply: {reply}")
    print("<----")

    if destination == "^all":
        # message was broadcast to all
        if sender in knownNodes:
            print(f"B/C Message from known node {sender}.")
            if message_type in ["connection_test", "help", "echo"]:
                send_reply = True
        else:
            print(f"B/C Message from unknown node {sender}")
            #in public channel limit replies to a few things such as connection_test, help, echo
            if message_type in ["connection_test", "help", "echo"]:
                send_reply = True
    else:
        #message was to us directly
        if sender in knownNodes:
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
