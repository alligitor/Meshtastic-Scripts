# this file, reads the json file that stored all the nodes. Looks for entries that have a BotTasticData field
# prints the values and also calculates the duration it took for repsonse to comeback
import json
from datetime import datetime


# Load from file
with open("/tmp/allNodes.json", 'r') as f:
    allNodes = json.load(f)

for nodeId in allNodes:
    print(f"Found node {nodeId}")
    node = allNodes[nodeId]
    if  node.get("BotTasticData") != None:
        sendTime = node.get("BotTasticData").get("TelemetryTimeSent")
        recvTime = node.get("BotTasticData").get("TelemetryTimeReceived")

        print(f" Send time {sendTime}")
        print(f" Recv time {recvTime}")

        if sendTime != None:
            st = datetime.fromisoformat(sendTime)

        if recvTime != None:
            rt = datetime.fromisoformat(recvTime)

        if sendTime != None and recvTime != None:
            print(f"Delay between recv and send: {rt - st}")
