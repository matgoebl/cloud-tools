#!/usr/bin/env python3
import fastavro
import click
import logging
import sys
import json

@click.group()
@click.option('-s', '--schema',  help='AVRO schema file to use (.avsc)', type=click.File('r'), required=True)
@click.option('-v', '--verbose', help="Be more verbose, can be repeated (up to 3 times).", count=True)
@click.pass_context
def avro_tool(ctx, schema, verbose):
    """AVRO Message Encoder/Decoder."""
    logging.basicConfig(level=logging.WARNING-10*verbose,handlers=[logging.StreamHandler()],format="[%(levelname)s] %(message)s")
    ctx.obj = {}
    ctx.obj['parsed_schema'] = fastavro.schema.load_schema(schema.name)


@avro_tool.command()
@click.pass_context
def dump(ctx):
    """Dump schema."""
    print(ctx.obj['parsed_schema'])


@avro_tool.command()
@click.pass_context
@click.option('-i', '--input',      help='Input AVRO file to decode (.avro)', type=click.File('rb'), required=True)
@click.option('-h', '--skipheader', help='Skip given amount of initial header bytes', type=int)
@click.option('-o', '--output',     help='Output data file (.json)', type=click.File('w'), default='-')
def dec(ctx, input, skipheader, output):
    """Decode an AVRO encoded payload to JSON."""
    if skipheader:
        header_bytes = input.read(skipheader)
        print(f"header: {header_bytes}", file=sys.stderr)
    decoded_payload = fastavro.schemaless_reader(input, ctx.obj['parsed_schema'])
    output.write(json.dumps(decoded_payload, indent=1))


@avro_tool.command()
@click.pass_context
@click.option('-i', '--input',  help='Input data file (.json)', type=click.File('r'), default='-')
@click.option('-o', '--output', help='Output AVRO payload file (.avro)', type=click.File('wb'), required=True)
def enc(ctx, input, output):
    """Encode JSON data to AVRO payload."""
    fastavro.schemaless_writer(output, ctx.obj['parsed_schema'], json.load(input))


if __name__ == '__main__':
    avro_tool(auto_envvar_prefix='AVRO_TOOL')
