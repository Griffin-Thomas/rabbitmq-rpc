import pika
import time
import json

sleepTime = 20 # seems to be good enough for server to boot up in time
print(' [*] Sleeping for ', sleepTime, ' seconds.')
time.sleep(sleepTime)

credentials = pika.PlainCredentials('admin', 'fpfrocks')
connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host='rabbitmq',
        credentials=credentials
    )
)

channel = connection.channel()

channel.queue_declare(queue='rpc_queue')


def fib(n):
    if n <= 1:
        return n
    else:
        return fib(n - 1) + fib(n - 2)


def on_request(ch, method, props, body):
    n = int(body)
    print(" [.] fib(%s)" % n)
    response = {}
    response[str(n)] = fib(n)
    print(" [.] calculated (%r)" % response)

    ch.basic_publish(exchange='',
                     routing_key=props.reply_to,
                     properties=pika.BasicProperties(
                        correlation_id=props.correlation_id),
                        body=json.dumps(response)
                    )
    ch.basic_ack(delivery_tag=method.delivery_tag)


channel.basic_qos(prefetch_count=1) # number of tasks at a time per worker
channel.basic_consume(queue='rpc_queue', on_message_callback=on_request) 

print(" [x] Awaiting RPC requests")
channel.start_consuming()