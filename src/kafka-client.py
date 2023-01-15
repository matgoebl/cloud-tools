#!/usr/bin/env python3
from kafka import KafkaConsumer, TopicPartition, KafkaProducer
import click
import os
import sys
import re
import datetime
import logging
import ssl
import math
import json
from yapsy.PluginManager import PluginManager, IPluginLocator
from yapsy.PluginFileLocator import PluginFileLocator, PluginFileAnalyzerMathingRegex

@click.group()
@click.option('-b', '--bootstrap', help='Kafka bootstrap server.', default='localhost:9093', show_default=True)
@click.option('-v', '--verbose',  count=True)
@click.option('-U', '--username', help='Kafka username.')
@click.option('-P', '--password', help='Kafka password.')
@click.option('-S', '--insecure', help='Do not verfy SSL.', is_flag=True)
@click.option('-M', '--dnsmap', help='Remap DNS names.')
@click.option('-I', '--pluginpath',    help='Load encoder/decoder plugins from given path.')
@click.pass_context
def kafka_client(ctx, bootstrap, username, password, insecure, dnsmap, pluginpath, verbose):
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

    ctx.obj['producer_args'] = conn_args
    ctx.obj['consumer_args'] = conn_args | {
        'group_id': None,
        'enable_auto_commit': False,
        'auto_offset_reset': 'earliest',
    }

    if dnsmap:
        import dnsremap
        dnsremap.dnsmap = dnsmap

    if pluginpath:
        locator = PluginFileLocator()
        locator.setAnalyzers([PluginFileAnalyzerMathingRegex('codec-plugin',r'.*.codec-plugin.py')])
        plugin_manager = PluginManager()
        plugin_manager.setPluginLocator(locator,[pluginpath])
        plugin_manager.collectPlugins()
        ctx.obj['plugin_manager'] = plugin_manager


@kafka_client.command()
@click.pass_context
def list(ctx):
    """List topics."""
    consumer = KafkaConsumer(**ctx.obj['consumer_args'])
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

    producer = KafkaProducer(**ctx.obj['producer_args'])
    logging.debug(f"Sending message: {key}={payload} headers:{headerlist}")
    producer.send(topic, key=key.encode('utf-8'), headers=headerlist, value=payload)
    producer.flush()


@kafka_client.command()
@click.option('-t', '--topic',         help='Topic to receive from.', required=True)
@click.option('-c', '--count',         help='Number of messages to receive (will be rounded to multiple of partitions).', type=int, default=1, show_default=True)
@click.option('-f', '--follow',        help='Wait for new messages.', is_flag=True)
@click.option('-j', '--jump',          help='Jump to given date and time.')
@click.option('-w', '--writefilepath', help='Write messages (.data), headers (.header) and keys (.key) to files named <topic>.<number> at the given path (e.g. "."). The header may contain string dumps, that cannot be transparently sent again via "send" command.')
@click.option('-k', '--key',           help='Filter for messages with the given key.')
@click.option('-s', '--searchpayload', help='Filter for message whose payload matches the given regex.')
@click.option('-S', '--searchheader',  help='Filter for message whose headers match the given regex.')
@click.option('-X', '--extractheader', help='Extract and output the given header field for each message.')
@click.option('-q', '--quiet',         help='By quiet.', is_flag=True)
@click.pass_context
def recv(ctx, topic, count, follow, jump, writefilepath, key, searchpayload, searchheader, extractheader, quiet):
    """Receive messages."""
    consumer = KafkaConsumer(**ctx.obj['consumer_args'])
    topicpartitions = [TopicPartition(topic, partition) for partition in consumer.partitions_for_topic(topic)]
    consumer.assign(topicpartitions)
    offsets = consumer.end_offsets(topicpartitions)
    if jump:
        ts = int( datetime.datetime.fromisoformat(jump).timestamp() * 1000 )

    num_partitions = len(topicpartitions)
    count_per_partition = math.ceil(count / num_partitions)
    count = count_per_partition * num_partitions
    count_max = 0
    for topicpartition in topicpartitions:
        end_offset = offsets.get(topicpartition)
        if jump:
            seek_offset = consumer.offsets_for_times({topicpartition: ts})[topicpartition].offset
        else:
            seek_offset = end_offset - count_per_partition
            if seek_offset < 0:
                seek_offset = 0
        count_max += end_offset - seek_offset
        consumer.seek(topicpartition, seek_offset)
    if count_max < count:
        count = count_max


    n = 0
    m = 0
    while n < count or follow:
        topic_msgs = consumer.poll(timeout_ms=1000)
        if len(topic_msgs) == 0 and not follow:
            break
        for topic, msgs in topic_msgs.items():
            for msg in msgs:
                if n < count or follow:
                    n = n + 1
                    logging.debug(f"Received message: {msg}")

                    if key and msg.key.decode('utf-8', 'ignore') != key:
                        continue

                    if searchpayload and not re.search(searchpayload, msg.value.decode('utf-8', 'ignore'), flags=re.IGNORECASE):
                        continue

                    headers = ""
                    for k,v in msg.headers:
                        try:
                            v = v.decode('utf-8','strict')
                        except:
                            pass
                        headers += f"{k}:{v}\n"
                        if extractheader and k == extractheader:
                            print(f"{k}:{v}")

                    headers_oneline = headers.removesuffix('\n').replace('\n',';')

                    if searchheader and not re.search('^'+searchheader+'$', headers, flags=re.IGNORECASE|re.MULTILINE):
                        continue

                    m = m + 1

                    decoded_payload = None
                    if 'plugin_manager' in ctx.obj:
                        for plugin in ctx.obj['plugin_manager'].getAllPlugins():
                            decoded_payload = plugin.plugin_object.decode(msg.value, topic.topic)
                            if decoded_payload:
                                break

                    dt = datetime.datetime.fromtimestamp(msg.timestamp//1000).replace(microsecond=msg.timestamp % 1000*1000).astimezone().isoformat()
                    if not quiet:
                        print("%s %s(%d)%d [%s] %s:%s%s" % (dt, topic.topic, topic.partition, msg.offset, headers_oneline, msg.key, msg.value, decoded_payload and " = "+str(decoded_payload) or ""))

                    if writefilepath:
                        basefilename = os.path.join(writefilepath, "%s.%05i" % (topic.topic,n))
                        logging.debug(f"Writing to {basefilename}.data, .header and .key")
                        with open(basefilename + '.data', 'wb') as f:
                            f.write(msg.value)
                        with open(basefilename + '.key', 'wb') as f:
                            f.write(msg.key)
                        with open(basefilename + '.header', 'w') as f:
                            f.write(headers)
                        if decoded_payload:
                            with open(basefilename + '.json', 'w') as f:
                                f.write(json.dumps(decoded_payload, indent=4, sort_keys=True, default=str))

    if key or searchpayload or searchheader:
        print(f"# filtered {m} of {n} received messages")


if __name__ == '__main__':
    kafka_client(auto_envvar_prefix='KAFKA_CLIENT')
