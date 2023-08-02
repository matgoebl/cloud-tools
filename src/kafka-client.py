#!/usr/bin/env python3
"""
A simple kafka commandline client written in python.
It sends and receives messages while optionally decoding them using plugins.

Copyright (c) 2022 Matthias Goebl (matthias dot goebl at goebl dot net)

Published under the Apache License Version 2.0

For details see https://github.com/matgoebl/cloud-tools/
"""

from kafka import KafkaConsumer, TopicPartition, KafkaProducer
import click
import os
import sys
import re
import datetime
import dateutil.relativedelta
import logging
import ssl
import math
import json
import ratelimiter
import codecs
from yapsy.PluginManager import PluginManager, IPluginLocator
from yapsy.PluginFileLocator import PluginFileLocator, PluginFileAnalyzerMathingRegex

timeout_secs = 1

@click.group(help=__doc__)
@click.option('-b', '--bootstrap', help='Kafka bootstrap server.', default='localhost:9093', show_default=True)
@click.option('-v', '--verbose',  count=True)
@click.option('-U', '--username', help='Kafka username.')
@click.option('-P', '--password', help='Kafka password.')
@click.option('-S', '--insecure', help='Do not verfy SSL.', is_flag=True)
@click.option('-M', '--dnsmap', help='Remap DNS names.')
@click.option('-I', '--pluginpath',    help='Load encoder/decoder plugins from given path.')
@click.pass_context
def kafka_client(ctx, bootstrap, username, password, insecure, dnsmap, pluginpath, verbose):
    logging.basicConfig(level=logging.WARNING-10*verbose,handlers=[logging.StreamHandler()],format="[%(levelname)s] %(message)s")
    cfg = {}
    ctx.obj = cfg

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

    cfg['producer_args'] = conn_args
    cfg['consumer_args'] = conn_args | {
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
        cfg['plugin_manager'] = plugin_manager

    return cfg


@kafka_client.command()
@click.pass_obj
def list(cfg):
    """List topics."""
    consumer = KafkaConsumer(**cfg['consumer_args'])
    topics = [topic for topic in consumer.topics()]
    topics.sort()
    for topic in topics:
        print(topic)


def complete_topics(ctx, param, incomplete):
    cfg = ctx.parent.invoke(kafka_client, **ctx.parent.params)
    consumer = KafkaConsumer(**cfg['consumer_args'])
    topics = [topic for topic in consumer.topics()]
    topics.sort()
    return [topic for topic in topics if topic.startswith(incomplete)]


def unescape_bin_str(data: bytes) -> str:
     return unescape_bin(data).decode('utf-8','backslashreplace')

def unescape_bin(data: bytes) -> bytes:
    return codecs.escape_decode( data )[0]

def unescape(data: str) -> bytes:
    return codecs.escape_decode( data.encode('utf-8') )[0]

def escape(data: bytes) -> str:
    return ( codecs.escape_encode(data)[0] ) .replace(b':',b'\\x3a')


@kafka_client.command()
@click.option('-t', '--topic',       help='Topic to send to.', required=True, shell_complete=complete_topics)
@click.option('-k', '--key',         help='Key to use for sending.', default=b'', show_default=True)
@click.option('-K', '--keyfile',     help='Read key from file.', type=click.File('rb'))
@click.option('-h', '--headers',     help='Header to set for every sent message, e.g. abc:123;xyz:987', default=b'')
@click.option('-p', '--payload',     help='Payload to send.', default=b'', show_default=True)
@click.option('-H', '--headersfile', help='Read headers from file.', type=click.File('rb'))
@click.option('-P', '--payloadfile', help='Read payload from file.', type=click.File('rb'))
@click.option('-r', '--rate',        help='Rate limit in requests per second (default: almost no limit)', type=int, default=999999999999)
@click.option('-m', '--multiline',   help='Read keys and payloads line-by-line from their files', is_flag=True)
@click.option('-c', '--count',       help='Number of messages to send (ignored in multiline mode).', type=int, default=1, show_default=True)
@click.pass_obj
def send(cfg, topic, key, keyfile, headers, headersfile, payload, payloadfile, rate, multiline, count):
    """Send messages."""
    if headersfile:
        headers = headersfile.read().rstrip(b'\n')
    else:
        headers = headers.encode('utf-8')

    headerlist = None
    if headers:
        headerlist = []
        for header in re.split(br'[;\n]', headers):
            k, v = header.split(b':',1)
            headerlist.append( (unescape_bin_str(k), unescape_bin(v)) )

    if not keyfile:
        key=unescape(key)
    elif not multiline:
        key = keyfile.read()

    if not payloadfile:
        payload = unescape(payload)
    elif not multiline:
        payload = payloadfile.read()

    producer = KafkaProducer(**cfg['producer_args'])

    rate_limiter = ratelimiter.RateLimiter(max_calls=rate, period=1)

    while count > 0:
        with rate_limiter:
            if multiline:
                if payloadfile:
                    payload = payloadfile.readline()
                    if not payload:
                        break
                    payload = payload.rstrip(b'\n')
                if keyfile:
                    key = keyfile.readline()
                    if not key:
                        break
                    key = key.rstrip(b'\n')
            else:
                count = count - 1
            logging.info(f"Sending message: {key}={payload} headers:{headerlist}")
            producer.send(topic, key=key, headers=headerlist, value=payload)

    producer.flush()


@kafka_client.command()
@click.option('-t', '--topic',         help='Topic to receive from.', required=True, shell_complete=complete_topics)
@click.option('-c', '--count',         help='Number of messages to receive (will be rounded to multiple of partitions).', type=int, default=1, show_default=True)
@click.option('-C', '--matchedcount',  help='Number of matched messages to receive.', type=int, default=None, show_default=True)
@click.option('-f', '--follow',        help='Wait for new messages.', is_flag=True)
@click.option('-j', '--jump',          help='Jump to given date and time, e.g. "2023-01-18 22:04:10". A single negative number will seek back the given number of seconds, e.g. "-60" will start a minute ago.')
@click.option('-w', '--writefilepath', help='Write messages (.data), headers (.header) and keys (.key) to files named <topic>.<number> at the given path (e.g. ".").')
@click.option('-k', '--key',           help='Filter for messages with the given key.')
@click.option('-s', '--searchpayload', help='Filter for message whose payload matches the given regex.')
@click.option('-S', '--searchheader',  help='Filter for message whose headers match the given regex.')
@click.option('-X', '--extractheader', help='Extract and output the given header field for each message.')
@click.option('-q', '--quiet',         help='By quiet.', is_flag=True)
@click.pass_obj
def recv(cfg, topic, count, matchedcount, follow, jump, writefilepath, key, searchpayload, searchheader, extractheader, quiet):
    """Receive messages."""
    consumer = KafkaConsumer(**cfg['consumer_args'])
    topicpartitions = [TopicPartition(topic, partition) for partition in consumer.partitions_for_topic(topic)]
    consumer.assign(topicpartitions)
    offsets = consumer.end_offsets(topicpartitions)
    if jump:
        if jump[0] == '-':
            jump_time = datetime.datetime.now() - dateutil.relativedelta.relativedelta(seconds=int(jump[1:]))
        else:
            jump_time = datetime.datetime.fromisoformat(jump)
        ts = int( jump_time.timestamp() * 1000 )

    num_partitions = len(topicpartitions)
    count_per_partition = math.ceil(count / num_partitions)
    count = count_per_partition * num_partitions
    for topicpartition in topicpartitions:
        end_offset = offsets.get(topicpartition)
        if jump:
            seek_result = consumer.offsets_for_times({topicpartition: ts})[topicpartition]
            if not seek_result:
                return
            seek_offset = seek_result.offset
        else:
            seek_offset = end_offset - count_per_partition
            if seek_offset < 0:
                seek_offset = 0
        consumer.seek(topicpartition, seek_offset)


    n = 0
    m = 0
    dt_first = None
    dt_last = None
    stop = False
    while not stop:
        topic_msgs = consumer.poll(timeout_ms=timeout_secs*1000)
        if len(topic_msgs) == 0 and not follow:
            break
        for topic, msgs in topic_msgs.items():
            for msg in msgs:
                if not dt_first:
                    dt_first = datetime.datetime.fromtimestamp(msg.timestamp//1000).replace(microsecond=0).astimezone().isoformat()

                if ( m < matchedcount if matchedcount else n < count ) or follow:
                    n = n + 1
                    logging.debug(f"Received message: {msg}")

                    if key and msg.key != unescape(key):
                        continue

                    headers = b''
                    for k,v in msg.headers:
                        k_ = escape(k.encode('utf-8'))
                        v_ = escape(v)
                        headers += k_ + b':' + v_ + b'\n'

                    if searchheader and not re.search('^' + searchheader + '$', headers.decode('ascii','backslashreplace'), flags=re.IGNORECASE|re.MULTILINE):
                        continue

                    m = m + 1

                    if extractheader == '':
                        print(escape(msg.key).decode('ascii','backslashreplace'))
                    elif extractheader:
                        v = b";".join( [ v for k,v in msg.headers if k == extractheader ] )
                        if len(v) > 0:
                            print(escape(v).decode('ascii','backslashreplace'))

                    if quiet and not writefilepath:
                        continue

                    decoded_payload = None
                    if 'plugin_manager' in cfg:
                        for plugin in cfg['plugin_manager'].getAllPlugins():
                            decoded_payload = plugin.plugin_object.decode(msg.value, topic.topic)
                            if decoded_payload:
                                break

                    if searchpayload:
                        if decoded_payload:
                            if not re.search(searchpayload, str(decoded_payload), flags=re.IGNORECASE):
                                continue
                        else:
                            if not re.search(searchpayload, msg.value.decode('ascii','backslashreplace'), flags=re.IGNORECASE):
                                continue

                    dt = datetime.datetime.fromtimestamp(msg.timestamp//1000).replace(microsecond=0).astimezone().isoformat()
                    if not quiet:
                        headers_oneline = headers.removesuffix(b'\n').replace(b'\n', b';').decode('ascii','backslashreplace')
                        print("%s %s(%d)%d [%s] %s:%s%s" % (dt, topic.topic, topic.partition, msg.offset, headers_oneline, msg.key, msg.value, decoded_payload and " = "+str(decoded_payload) or ""))

                    if writefilepath:
                        basefilename = os.path.join(writefilepath, "%s.%05i" % (topic.topic,n))
                        logging.debug(f"Writing to {basefilename}.data, .header and .key")
                        with open(basefilename + '.data', 'wb') as f:
                            f.write(msg.value)
                        with open(basefilename + '.key', 'wb') as f:
                            f.write(msg.key)
                        with open(basefilename + '.header', 'wb') as f:
                            f.write(headers)
                        if decoded_payload:
                            with open(basefilename + '.json', 'w') as f:
                                f.write(json.dumps(decoded_payload, indent=4, sort_keys=True, default=str))
                else:
                    stop = True
                    dt_last = datetime.datetime.fromtimestamp(msg.timestamp//1000).replace(microsecond=0).astimezone().isoformat()


    if ( key or searchpayload or searchheader) and not quiet:
        print(f"# filtered {m} of {n} received messages ({dt_first or 'never'} until {dt_last or 'now'})")


if __name__ == '__main__':
    kafka_client(auto_envvar_prefix='KAFKA_CLIENT')
