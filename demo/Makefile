export NAMESPACE=kafka-test
export IMAGEURL=ghcr.io/matgoebl/cloud-tools:latest
SRC=$(PWD)/../src
all: install forward tests forward-kill

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
export PIPENV_VENV_IN_PROJECT=1
export PIPENV_PIPFILE=$(SRC)/Pipfile
export PATH:=$(SRC):$(PATH)
export APP:=$(SRC)

forward:
	@echo "Forward bootstrap server and broker ports..."
	kubectl port-forward --namespace $(NAMESPACE) services/$(KAFKA_SERVICE) 9093:9093 >/dev/null &
	kubectl port-forward --namespace $(NAMESPACE) services/$(KAFKA_SERVICE) 19093:9093 >/dev/null &

forward-kill:
	-pkill -e -f "^kubectl port-forward --namespace $(NAMESPACE)"

tests:
	./tests.sh --with-setup-env

sh:
	pipenv shell


kinesis-demo:
	aws sts get-caller-identity --query Arn --output text --no-cli-pager
	-make kinesis-demo-stream kinesis-demo-client
	sleep 5
	make kinesis-demo-cleanup

kinesis-demo-cleanup:
	-aws kinesis delete-stream --stream-name TestStream --output text --no-cli-pager
	-aws kinesis delete-stream --stream-name TestStream2 --output text --no-cli-pager

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


cloud-tools-deploy: cloud-tools-destroy
	CLOUD_TOOLS_KAFKA_CLIENT_BOOTSTRAP=$(KAFKA_CLIENT_BOOTSTRAP) \
	CLOUD_TOOLS_KAFKA_CLIENT_INSECURE=$(KAFKA_CLIENT_INSECURE) \
	CLOUD_TOOLS_KAFKA_CLIENT_USERNAME=$(KAFKA_CLIENT_USERNAME) \
	CLOUD_TOOLS_KAFKA_CLIENT_PASSWORD=$(KAFKA_CLIENT_PASSWORD) \
	../cloud-tools-deploy.sh

cloud-tools-destroy:
	-../cloud-tools-deploy.sh -d


clean:
	rm -f tmp*

.PHONY: all install destroy forward forward-kill list send recv avro-demo clean cloud-tools-deploy cloud-tools-destroy
