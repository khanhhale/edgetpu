"""A demo to classify image.

For Raspberry Pi, you need to install 'feh' as image viewer:
sudo apt-get install feh

Example (Running under python-tflite-source/edgetpu_api directory):
python3.5 demo/face_detection.py --input='test_data/lena.jpg'

Where '--input' specifies the path of input image.
"""
import argparse
import os
import platform
import subprocess
from edgetpu.detection.engine import DetectionEngine
from PIL import Image
from PIL import ImageDraw
import json
import datetime
import random
import time
from googleiot import CloudIot

import datetime
import random
import time
from googleiot import CloudIot

#pip install paho-mqtt

def main():
  cloudIotInstance = CloudIot()
  args = cloudIotInstance.parse_command_line_args()
  dicInstance = dict()
  listInstance = list()
  listOfResults = list()

  # Detect with mobilenet v2 ssd.
  model = os.path.join(
      os.path.dirname(os.path.realpath(__file__)),
      '../test_data/mobilenet_ssd_v2_face_quant_postprocess_edgetpu.tflite')

  # Initialize engine.
  labels = {0: 'face', 1: 'background'}
  engine = DetectionEngine(model, labels)

  imgArr = args.input.split(";")

  # Open image.

  for imgStr in imgArr:
    img = Image.open(imgStr)
    draw = ImageDraw.Draw(img)

    # Run inference.
    ans = engine.DetectWithImage(img, threshold=0.05, relative_coord=False, top_k=10)

    if ans:
      index = 1
      for face in ans:
        dicItem = dict()
        dicItem['index'] = str(index)
        dicItem['type'] = face.label
        dicItem['score'] = str(face.score)
        dicItem['box'] = face.bounding_box.tolist()
        listInstance.append(dicItem)
        #print (face.label, ' score = ', face.score)
        #print ('box = ', face.bounding_box.tolist())
        draw.rectangle(face.bounding_box.flatten().tolist(), outline='red')
        index += 1

      inferDict = dict()
      inferDict["results"] = listInstance
      inferDict["category"] = "Detection"
      inferDict["image"] = img.filename
      listOfResults.append(inferDict)       
   
      
      img.save(str(index)+'-'+'face_detect_result.jpg')
      if platform.machine() == 'x86_64':
        # For gLinux, simply show the image.
        img.show()
      elif platform.machine() == 'armv7l':
        # For Raspberry Pi, you need to install 'feh' to display image.
        subprocess.Popen(['feh', str(index)+'-'+'face_detect_result.jpg'])
      else:
        print ('Please check face_detect_result.jpg')
      

    else:
      print ('No faces detected!')
  
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
