from flask import Flask
import logging
import pika
import uuid
import threading
import json

app = Flask(__name__)

# logging.basicConfig(level=logging.DEBUG)
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
        self.corr_id = str(uuid.uuid4())
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
        # print(self.response)
        return self.response


@app.route("/calculate/<payload>")
def calculate(payload):
    n = int(payload)
    fibonacci_rpc = FibonacciRpcClient()
    threading.Thread(target=fibonacci_rpc.call, args=(n,)).start()
    return "sent " + payload


# @app.route("/results/<id>") # how to get corr_id in frontend for a reference later??
@app.route("/results")
def send_results():
    key = list(queue.keys())[0] # get the first key (dicts are unordered but whatever)
    # key = the corr_id we want

    # app.logger.info(queue)
    # app.logger.info("hey")
    # app.logger.info(queue[key])

    return json.dumps(queue[key])


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
