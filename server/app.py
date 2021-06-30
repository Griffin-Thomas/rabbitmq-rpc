from flask import Flask, Response
import pika
# import uuid # should we use this or just a timestamp?
from datetime import datetime # for timestamp option: 15-Jun-2021 (22:18:36.435350)
# from pytz import timezone # to get US/Eastern timezone
import threading
import json

import logging
logging.basicConfig(level=logging.INFO) # info and debug

# eastern = timezone('US/Eastern')

app = Flask(__name__)

queue = {}

class FibonacciRpcClient(object):

    def __init__(self):
        self.credentials = pika.PlainCredentials('admin', 'fpfrocks')

        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='rabbitmq',
                credentials=self.credentials
            )
        )

        self.channel = self.connection.channel()

        result = self.channel.queue_declare('', exclusive=True)
        self.callback_queue = result.method.queue

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True)

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, n):
        self.response = None

        # UUID method
        # self.corr_id = str(uuid.uuid4())

        # Datetime method
        dateTimeObj = datetime.now() # tz = None
        timestampStr = dateTimeObj.strftime("%d-%b-%Y (%H:%M:%S.%f)")
        self.corr_id = timestampStr

        queue[self.corr_id] = {}
        self.channel.basic_publish(
            exchange='',
            routing_key='rpc_queue',
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=str(n))
        while self.response is None:
            self.connection.process_data_events()
        queue[self.corr_id] = json.loads(self.response.decode()) # must decode to convert to UTF-8
        return self.response


@app.route("/calculate/<payload>", methods=['GET'])
def calculate(payload):
    n = int(payload)
    fibonacci_rpc = FibonacciRpcClient()
    threading.Thread(target=fibonacci_rpc.call, args=(n,)).start()
    return "Sent " + payload


@app.route("/designs", methods=['GET'])
def send_designs():
    return json.dumps(queue)


@app.route("/designs/<id>", methods=['GET']) # how to get corr_id in frontend for a reference later?
def send_design(id):
    app.logger.info(id) # the corr_id

    if id in queue:
        return json.dumps(queue[id])
    
    return Response(status = 200) # no data found, but request was valid


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')