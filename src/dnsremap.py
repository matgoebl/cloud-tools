# This is a hack to locally remap dns queries:
# When using kubectl port-forward the dnsname of the received brokers must be remapped to localhost.
# An alternative solution is to edit /etc/hosts, but this requires root permissions.
# This hack has been tested with kafka-python 2.0.2.

from kafka import conn
import socket
import logging

dnsmap = ""

def remapped_dns_lookup(host, port, afi=socket.AF_UNSPEC):
    orig_name = host + ':' + str(port)
    for mapping in dnsmap.split(','):
        key, val = mapping.split('=')
        if key == orig_name:
            host, port = val.split(':')
    logging.debug(f"remapped {orig_name} to {host}:{port}")
    return list(filter(conn.is_inet_4_or_6, socket.getaddrinfo(host, port, afi, socket.SOCK_STREAM)))

conn.dns_lookup = remapped_dns_lookup
