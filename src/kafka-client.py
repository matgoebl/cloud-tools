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
@click.option('-t', '--topic',       help='Topic to send to.', required=True)
@click.option('-k', '--key',         help='Key to use for sending.', default='TEST', show_default=True)
@click.option('-h', '--headers',     help='Header to set for every sent message, e.g. abc:123;xyz:987')
@click.option('-p', '--payload',     help='Payload to send.', default='abc123', show_default=True)
@click.option('-H', '--headersfile', help='Read headers from file.', type=click.File('r'))
@click.option('-P', '--payloadfile', help='Read payload from file.', type=click.File('rb'))
@click.pass_context
def send(ctx, topic, key, headers, payload, headersfile, payloadfile):
    """Send message."""
    if payloadfile:
        payload = payloadfile.read()
    else:
        payload = payload.encode('utf-8')
    if headersfile:
        headers = headersfile.read().rstrip('\n')

    headerlist = None
    if headers:
        headerlist = []
        for header in re.split(r'[;\n]', headers):
            k, v = header.split(':')
            headerlist.append((k,v.encode('utf-8')))

    producer_args = {}
    producer = KafkaProducer(**ctx.obj['conn_args'], **producer_args)
    logging.debug(f"Sending message: {key}={payload} headers:{headerlist}")
    producer.send(topic, key=key.encode('utf-8'), headers=headerlist, value=payload)
    producer.flush()


default_writefile = "msg%05i"
@kafka_client.command()
@click.option('-t', '--topic',         help='Topic to receive from.', required=True)
@click.option('-c', '--count',         help='Number of messages to receive.', type=int, default=1, show_default=True)
@click.option('-f', '--follow',        help='Wait for new messages.', is_flag=True)
@click.option('-j', '--jump',          help='Jump to given date and time.')
@click.option('-w', '--writefile',     help='Write messages (.data), headers (.header) and key (.key) to files using the given pattern. "." is a shortcut for ' + default_writefile)
@click.option('-k', '--key',           help='Filter for messages with the given key.')
@click.option('-s', '--searchpayload', help='Filter for message whose payload matches the given regex.')
@click.option('-S', '--searchheader',  help='Filter for message whose headers match the given regex.')
@click.pass_context
def recv(ctx, topic, count, follow, jump, writefile, key, searchpayload, searchheader):
    """Receive messages."""
    consumer_args = {
        'group_id': None,
        'enable_auto_commit': False,
        'auto_offset_reset': 'earliest',
    }
    consumer = KafkaConsumer(**ctx.obj['conn_args'], **consumer_args)
    topicpartitions = [TopicPartition(topic, partition) for partition in consumer.partitions_for_topic(topic)]
    consumer.assign(topicpartitions)

    partition = 0  # TODO: handle more than one partition
    topicpartition = topicpartitions[0] #TopicPartition(topic=topic, partition=partition)
    offsets = consumer.end_offsets(topicpartitions)
    end_offset = offsets.get(topicpartition)
    if jump:
        ts = int( datetime.datetime.fromisoformat(jump).timestamp() * 1000 )
        seek_offset = consumer.offsets_for_times({topicpartition: ts})[topicpartition].offset
    else:
        seek_offset = end_offset - count
        if seek_offset < 0:
            seek_offset = 0
    if end_offset - seek_offset < count:
        count = end_offset - seek_offset
    consumer.seek(topicpartition, seek_offset)

    if writefile == '.':
        writefile = default_writefile

    n = 0
    while n < count or follow:
        topic_msgs = consumer.poll(timeout_ms=1000)
        for topic, msgs in topic_msgs.items():
            for msg in msgs:
                if n < count or follow:
                    n = n + 1
                    logging.debug(f"Received message: {msg}")
                    if key and msg.key.decode('utf-8') != key:
                        continue
                    if searchpayload and not re.search(searchpayload, msg.value.decode('utf-8'), flags=re.IGNORECASE):
                        continue
                    headers = ""
                    for header in msg.headers:
                        headers += f"{header[0]}:{header[1].decode('utf-8')}\n"
                    headers_oneline = headers.replace('\n',';')
                    if searchheader and not re.search(searchheader, headers_oneline, flags=re.IGNORECASE):
                        continue
                    dt = datetime.datetime.fromtimestamp(msg.timestamp//1000).replace(microsecond=msg.timestamp % 1000*1000).astimezone().isoformat()
                    print("%s %s(%d)%d [%s] %s:%s" % (dt, topic.topic, topic.partition, msg.offset, headers_oneline, msg.key, msg.value))
                    if writefile:
                        basefilename = writefile % n
                        logging.debug(f"Writing to {basefilename}.data and {basefilename}.header")
                        with open(basefilename + '.data', 'wb') as f:
                            f.write(msg.value)
                        with open(basefilename + '.key', 'wb') as f:
                            f.write(msg.key)
                        with open(basefilename + '.header', 'w') as f:
                            f.write(headers)


if __name__ == '__main__':
    kafka_client(auto_envvar_prefix='KAFKA_CLIENT')
