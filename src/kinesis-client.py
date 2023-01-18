#!/usr/bin/env python3
from kinesis.consumer import KinesisConsumer
from kinesis.producer import KinesisProducer
from aws_kinesis_agg.deaggregator import iter_deaggregate_records
import boto3
import base64
import signal
import click
import os
import sys
import re
import datetime
import dateutil
import time
import logging
import ssl
import math
import json
from yapsy.PluginManager import PluginManager, IPluginLocator
from yapsy.PluginFileLocator import PluginFileLocator, PluginFileAnalyzerMathingRegex

@click.group()
@click.option('-v', '--verbose',  count=True)
@click.option('-I', '--pluginpath',    help='Load encoder/decoder plugins from given path.')
@click.pass_context
def kinesis_client(ctx, pluginpath, verbose):
    """Receive messages."""
    logging.basicConfig(level=logging.WARNING-10*verbose,handlers=[logging.StreamHandler()],format="[%(levelname)s] %(message)s")
    ctx.obj = {}

    if pluginpath:
        locator = PluginFileLocator()
        locator.setAnalyzers([PluginFileAnalyzerMathingRegex('codec-plugin',r'.*.codec-plugin.py')])
        plugin_manager = PluginManager()
        plugin_manager.setPluginLocator(locator,[pluginpath])
        plugin_manager.collectPlugins()
        ctx.obj['plugin_manager'] = plugin_manager


@kinesis_client.command()
@click.pass_context
def list(ctx):
    """List topics."""
    os.system("aws kinesis list-streams --query StreamNames --no-cli-pager --output yaml")


@kinesis_client.command()
@click.option('-t', '--topic',       help='Topic to send to.', required=True)
@click.option('-k', '--key',         help='Key to use for sending.', default='TEST', show_default=True)
@click.option('-p', '--payload',     help='Payload to send.', default='abc123', show_default=True)
@click.option('-P', '--payloadfile', help='Read payload from file.', type=click.File('rb'))
@click.pass_context
def send(ctx, topic, key, payload, payloadfile):
    """Send message."""
    if payloadfile:
        payload = payloadfile.read()
    else:
        payload = payload.encode('utf-8')

    producer = KinesisProducer(stream_name=topic, buffer_time=0.5, max_count=1)
    logging.debug(f"Sending message: {key}={payload}")
    producer.put(partition_key=key, data=payload)
    time.sleep(1)
    producer.async_producer.process.terminate()


@kinesis_client.command()
@click.option('-t', '--topic',         help='Topic to receive from.', required=True)
@click.option('-c', '--count',         help='Number of messages to receive (will be rounded to multiple of partitions).', type=int, default=1, show_default=True)
@click.option('-f', '--follow',        help='Wait for new messages.', is_flag=True)
@click.option('-j', '--jump',          help='Jump to given date and time, e.g. "2023-01-18 22:04:10". A single negative number will seek back the given number of seconds, e.g. "-60" will start a minute ago.')
@click.option('-w', '--writefilepath', help='Write messages (.data), headers (.header) and keys (.key) to files named <topic>.<number> at the given path (e.g. "."). The header may contain string dumps, that cannot be transparently sent again via "send" command.')
@click.option('-k', '--key',           help='Filter for messages with the given key.')
@click.option('-s', '--searchpayload', help='Filter for message whose payload matches the given regex.')
@click.option('-q', '--quiet',         help='By quiet.', is_flag=True)
@click.pass_context
def recv(ctx, topic, count, follow, jump, writefilepath, key, searchpayload, quiet):
    """Receive messages."""
    if jump and jump[0] == '-':
        jump = ( datetime.datetime.now() - dateutil.relativedelta.relativedelta(seconds=int(jump[1:])) ).astimezone().isoformat()

    consumer = KinesisConsumer(stream_name=topic, start_at_timestamp=jump)

    n = 0
    m = 0
    if not follow:
        reset_timeout()
    for msgs in consumer:
        for msg in iter_deaggregate_records(msgs,data_format='Boto3'):
            if n >= count and not follow:
                stop = True
                break

            payload = msg['kinesis']['data']
            if 'aggregated' in msg['kinesis'] and msg['kinesis']['aggregated'] == True:
                payload = base64.b64decode(payload)

            n = n + 1
            logging.debug(f"Received message: {msg}: {payload}")

            if key and msg.key.decode('utf-8', 'ignore') != key:
                continue

            if searchpayload and not re.search(searchpayload, msg.value.decode('utf-8', 'ignore'), flags=re.IGNORECASE):
                continue

            m = m + 1

            decoded_payload = None
            if 'plugin_manager' in ctx.obj:
                for plugin in ctx.obj['plugin_manager'].getAllPlugins():
                    decoded_payload = plugin.plugin_object.decode(msg.value, topic.topic)
                    if decoded_payload:
                        break

            dt = msg['kinesis']['approximateArrivalTimestamp'].replace(microsecond=0).astimezone().isoformat()
            if not quiet:
                print("%s %s %s:%s%s" % (dt, msg['kinesis']['sequenceNumber'], msg['kinesis']['partitionKey'], payload, decoded_payload and " = "+str(decoded_payload) or ""))

            if writefilepath:
                basefilename = os.path.join(writefilepath, "%s.%05i" % (topic.topic,n))
                logging.debug(f"Writing to {basefilename}.data, .header and .key")
                with open(basefilename + '.data', 'wb') as f:
                    f.write(msg.value)
                with open(basefilename + '.key', 'wb') as f:
                    f.write(msg.key)
                if decoded_payload:
                    with open(basefilename + '.json', 'w') as f:
                        f.write(json.dumps(decoded_payload, indent=4, sort_keys=True, default=str))

        if n >= count and not follow:
            break
        if not follow:
            reset_timeout()
    
    if key or searchpayload:
        print(f"# filtered {m} of {n} received messages")

    consumer.shutdown()

def reset_timeout():
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(1)

def timeout_handler(signum, stack):
    raise KeyboardInterrupt


if __name__ == '__main__':
    kinesis_client(auto_envvar_prefix='KINESIS_CLIENT')
