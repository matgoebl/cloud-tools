#!/usr/bin/env python3
from kafka import KafkaConsumer, TopicPartition, KafkaProducer
import click
import os
import sys
import re
import datetime
import logging
import ssl

@click.group()
@click.option('-b', '--bootstrap', help='Kafka bootstrap server.', default='localhost:9093', show_default=True)
@click.option('-v', '--verbose',  count=True)
@click.option('-U', '--username', help='Kafka username.')
@click.option('-P', '--password', help='Kafka password.')
@click.option('-S', '--insecure', help='Do not verfy SSL.', is_flag=True)
@click.option('-M', '--dnsmap', help='Remap DNS names.')
@click.pass_context
def kafka_client(ctx, bootstrap, username, password, insecure, dnsmap, verbose):
    """Receive messages."""
    logging.basicConfig(level=logging.WARNING-10*verbose,handlers=[logging.StreamHandler()],format="[%(levelname)s] %(message)s")
    ctx.obj = {}

    conn_args = {
        'bootstrap_servers': [bootstrap],
        'client_id': os.path.basename(sys.argv[0]) + "@" + os.uname().nodename,
    }

    if insecure:
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        conn_args = conn_args | {
            'ssl_check_hostname': False,
            'ssl_context': ssl_context,
        }

    if username:
        conn_args = conn_args | {
            'security_protocol': 'SASL_SSL',
            'sasl_mechanism': 'SCRAM-SHA-512',
            'sasl_plain_username': username,
            'sasl_plain_password': password,
        }

    ctx.obj['conn_args'] = conn_args

    if dnsmap:
        import dnsremap
        dnsremap.dnsmap = dnsmap


@kafka_client.command()
@click.pass_context
def list(ctx):
    """List topics."""
    consumer = KafkaConsumer(**ctx.obj['conn_args'])
    topics = [topic for topic in consumer.topics()]
    topics.sort()
    for topic in topics:
        print(topic)


@kafka_client.command()
@click.option('-t', '--topic',   help='Topic to send to.', required=True)
@click.option('-k', '--key',     help='Key to use for sending.', default='TEST', show_default=True)
@click.option('-h', '--headers', help='Header to set for every sent message, e.g. abc:123;xyz:987')
@click.option('-p', '--payload', help='Payload to send.', default='abc123', show_default=True)
@click.pass_context
def send(ctx, topic, key, headers, payload):
    """Send message."""
    producer_args = {
    }
    producer = KafkaProducer(**ctx.obj['conn_args'], **producer_args)
    headerlist = None
    if headers:
        headerlist = []
        for header in re.split(r'[;\n]', headers):
            key, val = header.split(':')
            headerlist.append((key,val.encode('utf-8')))
    print(headerlist)
    producer.send(topic, key=key.encode('utf-8'), headers=headerlist, value=payload.encode('utf-8'))
    producer.flush()


@kafka_client.command()
@click.option('-t', '--topic', help='Topic to receive from.', required=True)
@click.option('-c', '--count', help='Number of messages to receive.', type=int, default=1)
@click.pass_context
def recv(ctx, topic, count):
    """Receive messages."""
    consumer_args = {
        'group_id': None,
        'enable_auto_commit': False,
        'auto_offset_reset': 'earliest',
    }
    consumer = KafkaConsumer(**ctx.obj['conn_args'], **consumer_args)
    topicpartition = TopicPartition(topic, 0)
    consumer.assign([topicpartition])
    consumer.seek_to_end((topicpartition))
    offset_end = consumer.position(topicpartition)
    consumer.seek(topicpartition, offset_end - count)

    while count > 0:
        topic_msgs = consumer.poll(timeout_ms=1000)
        for topic, msgs in topic_msgs.items():
            for msg in msgs:
                if count > 0:
                    dt = datetime.datetime.fromtimestamp(msg.timestamp//1000).replace(microsecond=msg.timestamp % 1000*1000).astimezone().isoformat()
                    print("%s %s(%d)%d: %s=%s" % (dt, topic.topic, topic.partition, msg.offset, msg.key, msg.value))
                    print(msg)
                    count = count - 1


if __name__ == '__main__':
    kafka_client(auto_envvar_prefix='KAFKA_CLIENT')
