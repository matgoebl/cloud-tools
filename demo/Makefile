export NAMESPACE=kafka-test
export IMAGEURL=ghcr.io/matgoebl/cloud-tools:latest
SRC=$(PWD)/../src
all: install forward list send recv forward-kill

install:
	@echo -n "Installing on Cluster: "
	@kubectl cluster-info | head -n1
	-kubectl create namespace $(NAMESPACE)
	kubectl --namespace $(NAMESPACE) apply -f "https://strimzi.io/install/latest?namespace=$(NAMESPACE)"
	kubectl --namespace $(NAMESPACE) apply -f kafka-cluster.yaml
	kubectl --namespace $(NAMESPACE) apply -f kafka-users.yaml

destroy:
	-kubectl delete namespace $(NAMESPACE)


export KAFKA_SERVICE=my-cluster-kafka-brokers
export KAFKA_CLIENT_BOOTSTRAP=my-cluster-kafka-0.$(KAFKA_SERVICE).$(NAMESPACE).svc:9093
export KAFKA_CLIENT_DNSMAP=$(KAFKA_CLIENT_BOOTSTRAP)=localhost:9093
export KAFKA_CLIENT_INSECURE=true
export KAFKA_CLIENT_USERNAME=demo-user
export KAFKA_CLIENT_PASSWORD=$(shell kubectl --namespace $(NAMESPACE) get secret/$(KAFKA_CLIENT_USERNAME) -o json | jq .data.password -r | base64 -d)
export ENV PIPENV_VENV_IN_PROJECT=1
export PATH:=$(SRC):$(PATH)

forward:
	@echo "Forward bootstrap server and broker ports..."
	kubectl port-forward --namespace $(NAMESPACE) services/$(KAFKA_SERVICE) 9093:9093  & 
	kubectl port-forward --namespace $(NAMESPACE) services/$(KAFKA_SERVICE) 19093:9093 &

forward-kill:
	pkill -e -f "^kubectl port-forward --namespace $(NAMESPACE)"

list:
	pipenv run kafka-client.py list

send:
	pipenv run kafka-client.py send -t demo-topic -k TEST-KEY -h 'abc:123;xyz:987' -p 'Hello World!'

recv:
	pipenv run kafka-client.py -v recv -t demo-topic -c 3

sh:
	pipenv shell


AVRO_TOOLS=java -jar $(SRC)/.venv/avro-tools-1.11.1.jar
avro-demo:
	$(AVRO_TOOLS) idl2schemata ./demo.avdl ./
	$(AVRO_TOOLS) fromjson --schema-file demo.avsc demo.json > tmp_demo.avro
	$(AVRO_TOOLS) tojson tmp_demo.avro
	pipenv run avro-tool.py -s demo.avsc dump
	pipenv run avro-tool.py -s demo.avsc enc -i demo.json -o tmp_demo_schemaless.avro
	hexdump -c tmp_demo_schemaless.avro
	pipenv run avro-tool.py -s demo.avsc dec -i tmp_demo_schemaless.avro

avrosend:
	pipenv run kafka-client.py send -t demo -P tmp_demo_schemaless.avro

avrorecv:
	pipenv run kafka-client.py -I $(SRC) -v recv -t demo -c 1 -w .

avroglue:
	@echo 'Test uncompressed:'
	(echo 03 00 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 02 | xxd -r -p; cat tmp_demo_schemaless.avro ) > tmp_demo_schemaless_glueenc.avro
	hexdump -C tmp_demo_schemaless_glueenc.avro
	cp demo.avsc demo.00000000-0000-0001-0000-000000000002.avsc
	pipenv run kafka-client.py send -t demo -P tmp_demo_schemaless_glueenc.avro
	pipenv run kafka-client.py -I $(SRC) recv -t demo -c 1 -w .

	@echo 'Test compressed:'
	(echo 03 05 00 00 00 00 00 00 00 01 00 00 00 00 00 00 00 02 | xxd -r -p; pigz -z < tmp_demo_schemaless.avro ) > tmp_demo_schemaless_glueenczip.avro
	hexdump -C tmp_demo_schemaless_glueenczip.avro
	pipenv run kafka-client.py send -t demo -P tmp_demo_schemaless_glueenczip.avro
	pipenv run kafka-client.py -I $(SRC) recv -t demo -c 1 -w .


kinesis-demo:
	aws sts get-caller-identity --query Arn --output text --no-cli-pager
	-make kinesis-demo-stream kinesis-demo-client
	sleep 5
	make kinesis-demo-cleanup

kinesis-demo-cleanup:
	aws kinesis delete-stream --stream-name TestStream --output text --no-cli-pager
	aws kinesis delete-stream --stream-name TestStream2 --output text --no-cli-pager

kinesis-demo-stream:
	make kinesis-demo-cleanup || true
	sleep 5
	aws kinesis create-stream --stream-name TestStream --shard-count 1 --output json  --no-cli-pager
	aws kinesis create-stream --stream-name TestStream2 --shard-count 1 --output json  --no-cli-pager
	sleep 5
	aws kinesis list-streams --output json --no-cli-pager
	aws kinesis describe-stream-summary --stream-name TestStream --output json --no-cli-pager
	aws kinesis put-record --stream-name TestStream --partition-key TEST-KEY1 --data 'Hello World!' --cli-binary-format raw-in-base64-out --output json --no-cli-pager
	aws kinesis get-records --shard-iterator `aws kinesis get-shard-iterator --shard-id shardId-000000000000 --shard-iterator-type TRIM_HORIZON --stream-name TestStream --query 'ShardIterator'` --output json | jq -r '.Records[].Data' | while read data; do echo "$$data" | base64 --decode; echo; done

kinesis-demo-client:
	pipenv run kinesis-client.py send -t TestStream -k TEST-KEY2 -p 'Hello World :-)'
	pipenv run kinesis-client.py recv -t TestStream -j -60 -c 10


cloud-tools-deploy:
	CLOUD_TOOLS_KAFKA_CLIENT_BOOTSTRAP=$(KAFKA_CLIENT_BOOTSTRAP) \
	CLOUD_TOOLS_KAFKA_CLIENT_USERNAME=$(KAFKA_CLIENT_USERNAME) \
	CLOUD_TOOLS_KAFKA_CLIENT_PASSWORD=$(KAFKA_CLIENT_PASSWORD) \
	../cloud-tools-deploy.sh

cloud-tools-destroy:
	../cloud-tools-deploy.sh -d


clean:
	rm -f tmp*

.PHONY: all install destroy forward forward-kill list send recv avro-demo clean cloud-tools-deploy cloud-tools-destroy
