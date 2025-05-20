# this file, reads the json file that stored all the nodes. Looks for entries that have a BotTasticData field
# prints the values and also calculates the duration it took for repsonse to comeback
import json
from datetime import datetime

def getTimeStamps(key, data):
    fullSentKey = key + "TimeSent"
    fullRecvKey = key + "TimeReceived"

    sendTime = data.get(fullSentKey)
    recvTime = data.get(fullRecvKey)

    print(f" {key} Send time {sendTime}")
    print(f" {key} Recv time {recvTime}")

    if sendTime != None:
        st = datetime.fromisoformat(sendTime)

    if recvTime != None:
        rt = datetime.fromisoformat(recvTime)

    if sendTime != None and recvTime != None:
        print(f"  {key} delay between recv and send: {rt - st}")

def main():
    # Load from file
    with open("/tmp/allNodes.json", 'r') as f:
        allNodes = json.load(f)

    for nodeId in allNodes:
        print(f"Found node {nodeId}")
        node = allNodes[nodeId]
        botTasticData = node.get("BotTasticData")
        if  botTasticData != None:
            getTimeStamps("Telemetry", botTasticData)
            getTimeStamps("TraceRoute", botTasticData)
        else:
            print(f"Node without BotTasticData: {nodeId}")

if __name__ == "__main__":
    main()
