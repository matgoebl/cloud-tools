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

cloud-tools-deploy:
	../cloud-tools-deploy.sh

cloud-tools-destroy:
	../cloud-tools-deploy.sh -d


clean:
	rm -f tmp*

.PHONY: all install destroy forward forward-kill list send recv avro-demo clean cloud-tools-deploy cloud-tools-destroy
