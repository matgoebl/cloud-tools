#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

if [ "${1:-}" == "--with-setup-env" ]; then
  source ../src/.venv/bin/activate
  export PATH=$PATH:../src
fi
set -x

echo '*** Test list:'
kafka-client.py list

echo '*** Test send:'
kafka-client.py send -t demo-topic -k TEST-KEY -h 'abc:123;xyz:987' -p 'Hello World!'

echo '*** Test recv:'
kafka-client.py recv -t demo-topic -c 3

echo '*** Test avro-tool:'
avro-tools.sh idl2schemata ./demo.avdl ./
avro-tools.sh fromjson --schema-file demo.avsc demo.json > tmp_demo.avro
avro-tools.sh tojson tmp_demo.avro
avro-tool.py -s demo.avsc dump
avro-tool.py -s demo.avsc enc -i demo.json -o tmp_demo_schemaless.avro
xxd tmp_demo_schemaless.avro
avro-tool.py -s demo.avsc dec -i tmp_demo_schemaless.avro
echo

echo '*** Test avrosend:'
kafka-client.py send -t demo -P tmp_demo_schemaless.avro

echo '*** Test avrorecv:'
kafka-client.py -I ${APP:-/app} recv -t demo -c 1 -w .

echo '*** Test avroglue uncompressed:'
(echo 03 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 02 | xxd -r -p; cat tmp_demo_schemaless.avro ) > tmp_demo_schemaless_glueenc.avro
xxd tmp_demo_schemaless_glueenc.avro
cp demo.avsc demo.00000000-0000-0001-0000-000000000002.avsc
kafka-client.py send -t demo -P tmp_demo_schemaless_glueenc.avro
kafka-client.py -I . recv -t demo -c 1 -w .

echo '*** Test avroglue compressed:'
(echo 03 05 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 02 | xxd -r -p; pigz -z < tmp_demo_schemaless.avro ) > tmp_demo_schemaless_glueenczip.avro
xxd tmp_demo_schemaless_glueenczip.avro
kafka-client.py send -t demo -P tmp_demo_schemaless_glueenczip.avro
kafka-client.py -I ${APP:-/app} recv -t demo -c 1 -w .

echo '*** Tests done.'
rm -f tmp*
