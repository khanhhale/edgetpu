"""A demo to classify image."""
import argparse
from edgetpu.classification.engine import ClassificationEngine
from PIL import Image
import json
import datetime
import os
import random
import time
from googleiot import CloudIot

# Function to read labels from text files.
def ReadLabelFile(file_path):
  with open(file_path, 'r') as f:
    lines = f.readlines()
  ret = {}
  for line in lines:
    pair = line.strip().split(maxsplit=1)
    ret[int(pair[0])] = pair[1].strip()
  return ret


def main():
  cloudIotInstance = CloudIot()
  args = cloudIotInstance.parse_command_line_args()  
  dicInstance = dict()
  listInstance = list()
  listOfResults = list()
  # Prepare labels.
  labels = ReadLabelFile(args.label)

  # Initialize engine.
  engine = ClassificationEngine(args.model, labels)

  # Run inference.
  imgArr = args.image.split(";")
 
  index = 1
  for imgStr in imgArr:
    img = Image.open(imgStr)
    
    for result in engine.ClassifyWithImage(img, top_k=3):
      dicItem = dict()
      dicItem['label'] = str(result[0])
      dicItem['type'] = result[1]
      dicItem['score'] = str(result[2])
      listInstance.append(dicItem)
    
    inferDict = dict()
    inferDict["results"] = listInstance
    inferDict["category"] = "Classification"
    inferDict["image"] = img.filename
    listOfResults.append(inferDict)     
    index += 1
 	
  listInstance.reverse()
  # Publish to the events or state topic based on the flag.

  sub_topic = 'events' if args.message_type == 'event' else 'state'
  mqtt_topic = '/devices/{}/{}'.format(args.device_id, sub_topic)

  jwt_iat = datetime.datetime.utcnow()
  jwt_exp_mins = args.jwt_expires_minutes

  client = cloudIotInstance.get_client(
        args.project_id, args.cloud_region, args.registry_id, args.device_id,
        args.private_key_file, args.algorithm, args.ca_certs,
        args.mqtt_bridge_hostname, args.mqtt_bridge_port)
  
  for i in range(1, len(listOfResults) + 1):
        # Process network events.
        client.loop()

        # Wait if backoff is required.
        if cloudIotInstance.should_backoff:
            # If backoff time is too large, give up.
            if cloudIotInstance.minimum_backoff_time > cloudIotInstance.MAXIMUM_BACKOFF_TIME:
                print('Exceeded maximum backoff time. Giving up.')
                break

            # Otherwise, wait and connect again.
            delay = cloudIotInstance.minimum_backoff_time + random.randint(0, 1000) / 1000.0
            print('Waiting for {} before reconnecting.'.format(delay))
            time.sleep(delay)
            cloudIotInstance.minimum_backoff_time *= 2
            client.connect(args.mqtt_bridge_hostname, args.mqtt_bridge_port)

        
        payload = json.dumps(listOfResults.pop())
        print('Publishing message \'{}\''.format(payload))

        seconds_since_issue = (datetime.datetime.utcnow() - jwt_iat).seconds
        if seconds_since_issue > 60 * jwt_exp_mins:
            print('Refreshing token after {}s').format(seconds_since_issue)
            jwt_iat = datetime.datetime.utcnow()
            client = cloudIotInstance.get_client(args.project_id, args.cloud_region,args.registry_id, args.device_id, args.private_key_file,args.algorithm, args.ca_certs, args.mqtt_bridge_hostname, args.mqtt_bridge_port)
        # [END iot_mqtt_jwt_refresh]
        # Publish "payload" to the MQTT topic. qos=1 means at least once
        # delivery. Cloud IoT Core also supports qos=0 for at most once
        # delivery.

        client.publish(mqtt_topic, payload, qos=1)

        # Send events every second. State should not be updated as often
        time.sleep(1 if args.message_type == 'event' else 5)  
  
if __name__ == '__main__':
  main()
