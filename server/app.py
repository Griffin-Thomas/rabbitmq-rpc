from flask import Flask, Response
import pika
# import uuid # should we use this or just a timestamp? I think timestamp
from datetime import datetime # for timestamp option: 15-Jun-2021 (22:18:36.435350)
# from pytz import timezone # to get a specific timezone perhaps
import threading
import json

import logging
logging.basicConfig(level=logging.INFO) # info and debug with this level

# eastern = timezone('US/Eastern')

app = Flask(__name__)

# TODO: get queue from PostgreSQL either here or probably inside FpfRpcClient class
queue = {} # RabbitMQ queue that stores the messages

class FpfRpcClient(object):

    def __init__(self):
        self.credentials = pika.PlainCredentials('admin', 'fpfrocks')

        self.connection = pika.BlockingConnection(
            pika.ConnectionParameters(
                host='rabbitmq',
                credentials=self.credentials
            )
        )

        self.channel = self.connection.channel()

        # TODO: self.queue = ... from PostgreSQL, instead of outside the class

        result = self.channel.queue_declare('', exclusive=True)
        self.callback_queue = result.method.queue

        self.channel.basic_consume(
            queue=self.callback_queue,
            on_message_callback=self.on_response,
            auto_ack=True)

    def on_response(self, ch, method, props, body):
        if self.corr_id == props.correlation_id:
            self.response = body

    def call(self, payload, id):
        self.response = None
        self.corr_id = id

        queue[self.corr_id] = {}
        # TODO: also create entry in PostgreSQL

        self.channel.basic_publish(
            exchange='',
            routing_key='rpc_queue',
            properties=pika.BasicProperties(
                reply_to=self.callback_queue,
                correlation_id=self.corr_id,
            ),
            body=str(payload))
        while self.response is None:
            self.connection.process_data_events()
        
        queue[self.corr_id] = json.loads(self.response.decode()) # must decode to convert to UTF-8
        # TODO: also update entry in PostgreSQL based on correlation ID

        return self.response


@app.route("/calculate/<payload>", methods=['GET'])
@app.route("/calculate/<payload>/<id>", methods=['GET'])
def calculate(payload, id=None):
    '''
    calculate - To call the RabbitMQ RPC

    @param payload <json> - A JSON containing the FPF payload required to generate a path via our Main REST API
    @param @optional id <str> - A timestamp to serve as the correlation ID for our message
        e.g. To set a Correlation ID on each produced message (on consumer you receive this 
        Correlation ID and you can match it back), then check if that's the one you are expecting
    
    @return <str> - To confirm the correlation ID (time) that the payload was sent at, OR 400 response code
                    if the payload is bad
    '''
    try:
        payload = int(payload) # TODO: temporary int of course
    except ValueError:
        return Response(status=400) # invalid payload request

    # UUID method for messages
    # self.corr_id = str(uuid.uuid4())

    # Datetime method for messages
    # TODO: bring to the caller (web app) instead of this function
    if id is None:
        dateTimeObj = datetime.now() # tz = None
        id = dateTimeObj.strftime("%d-%b-%Y (%H:%M:%S.%f)") # e.g. 15-Jun-2021 (22:18:36.435350)

    fibonacci_rpc = FpfRpcClient()
    threading.Thread(target=fibonacci_rpc.call, args=(payload,id,)).start()
    return "Sent on " + id


@app.route("/designs", methods=['GET'])
@app.route("/designs/<id>", methods=['GET'])
def results(id=None):
    '''
    results - Send back the design associated with a correlation ID, or all designs

    @param @optional id <str> - The correlation ID (timestamp)

    @return <json> - The design(s) made via the RPC, OR just a 200 response code if no design exists
    '''
    # app.logger.info(id) # the correlation ID

    if id is None: # send back all designs made via the RPC
        # TODO: get the queue (all entries) from PostgreSQL
        # queue = ...
        return json.dumps(queue)

    if id in queue: # send back specific design made via the RPC
        # TODO: get the queue (specific entry) from PostgreSQL
        return json.dumps(queue[id])
    
    return Response(status=200) # no data found for given correlation ID, but request was valid


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')