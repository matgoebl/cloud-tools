export NAMESPACE=kafka-test

all:

install:
	@echo -n "Installing on Cluster: "
	@kubectl cluster-info | head -n1
	-kubectl create namespace $(NAMESPACE)
	kubectl --namespace $(NAMESPACE) apply -f "https://strimzi.io/install/latest?namespace=$(NAMESPACE)"
	kubectl --namespace $(NAMESPACE) apply -f kafka-cluster.yaml
	kubectl --namespace $(NAMESPACE) apply -f kafka-users.yaml

destroy:
	-kubectl delete namespace $(NAMESPACE)

.PHONY: all install destroy
	