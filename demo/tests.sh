#!/bin/bash
set -euo pipefail
IFS=$'\n\t'

if [ "${1:-}" == "--with-setup-env" ]; then
  source ../src/.venv/bin/activate
  export PATH=$PATH:$PWD/../src
fi
set -x

mkdir -p tests-out
cd tests-out

echo '*** Test list:'
kafka-client.py list

echo '*** Test send:'
kafka-client.py send -t demo-topic -k TEST-KEY1 -h 'abc:123;xyz:987' -p 'Hello World!'
kafka-client.py send -t demo-topic -k TEST-KEY2 -h 'abc:456;xyz:987' -p 'Hello World!'
kafka-client.py send -t demo-topic -k 'TEST-KEY\x33' -h 'abc:78\x39;xyz:987' -p 'Hello World\x21'

echo '*** Test recv:'
kafka-client.py recv -t demo-topic -c 3 -s Hello | grep Hello
kafka-client.py recv -t demo-topic -c 3 -k TEST-KEY1 -X '' -q | grep TEST-KEY1
kafka-client.py recv -t demo-topic -c 3 -S 'abc:123' -X abc -q | grep abc:123
kafka-client.py recv -t demo-topic -c 3 -k 'TEST\x2dKEY3' -X '' -q | grep TEST-KEY3
kafka-client.py recv -t demo-topic -c 3 -S '\x61bc:\x3789' -X abc -q | grep abc:789

echo '*** Test send & receive from files:'
kafka-client.py send -t demo-topic -K ../demo.key -H ../demo.header -P ../demo.data
rm -rf demo-topic.0*
kafka-client.py recv -t demo-topic -c 1 -w .
for i in key header data; do diff -u ../demo.$i ./demo-topic.00001.$i; done

echo '*** Test avro-tool:'
avro-tools.sh idl2schemata ../demo.avdl ./
avro-tools.sh fromjson --schema-file demo.avsc ../demo.json > demo.avro
avro-tools.sh tojson demo.avro > demo.json
diff -u <(jq -S < ../demo.json) <(jq -S < demo.json)
avro-tool.py -s demo.avsc dump
avro-tool.py -s demo.avsc enc -i demo.json -o demo_schemaless.avro
xxd demo_schemaless.avro
avro-tool.py -s demo.avsc dec -i demo_schemaless.avro > demo2.json
diff -u <(jq -S < demo.json) <(jq -S < demo2.json)
echo

echo '*** Test avrosend:'
kafka-client.py send -t demo -P demo_schemaless.avro

echo '*** Test avrorecv:'
kafka-client.py -I ${APP:-/app} recv -t demo -c 1 -w . | grep "'hello': 'World!'"

echo '*** Test avroglue uncompressed:'
(echo 03 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 02 | xxd -r -p; cat demo_schemaless.avro ) > demo_schemaless_glueenc.avro
xxd demo_schemaless_glueenc.avro
kafka-client.py send -t demo -P demo_schemaless_glueenc.avro
rm -rf demo.0*
cp demo.avsc demo.00000000-0000-0001-0000-000000000002.avsc
kafka-client.py -I . recv -t demo -c 1 -w .
grep -q World demo.00001.data

echo '*** Test avroglue compressed:'
(echo 03 05 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 02 | xxd -r -p; pigz -z < demo_schemaless.avro ) > demo_schemaless_glueenczip.avro
xxd demo_schemaless_glueenczip.avro
kafka-client.py send -t demo -P demo_schemaless_glueenczip.avro
rm -rf demo.0*
cp demo.avsc demo.00000000-0000-0001-0000-000000000002.avsc
kafka-client.py -I ${APP:-/app} recv -t demo -c 1 -w .
grep -q World demo.00001.json

echo '*** Test rate limited:'
test `/usr/bin/time -f '%e' kafka-client.py send -t demo -c 6 -r 2 2>&1 | sed -e 's/\..*//'` -ge 2

echo '*** Tests done.'
cd ..
rm -rf tests-out
