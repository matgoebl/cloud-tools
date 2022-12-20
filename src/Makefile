export IMAGE=$(shell cd .. && basename $$PWD)
export BUILDTAG:=$(shell date +%Y%m%d.%H%M%S)
export ENV PIPENV_VENV_IN_PROJECT=1
VENV=.venv

all: image

$(VENV):
	python3 -m pip install --user virtualenv pipenv
	pipenv install
	cd .venv/ && wget --continue https://repo1.maven.org/maven2/org/apache/avro/avro-tools/1.11.1/avro-tools-1.11.1.jar

sh: $(VENV)
	pipenv shell

clean:
	rm -rf $(VENV)
	find -iname "*.pyc" -delete 2>/dev/null || true
	find -name __pycache__ -type d -exec rm -rf '{}' ';' 2>/dev/null || true

distclean: clean
	rm -rf Pipfile.lock

image: $(VENV)
	docker build --build-arg BUILDTAG=$(BUILDTAG) -t $(IMAGE) .
	docker tag $(IMAGE) $(DOCKER_REGISTRY)/$(IMAGE):$(BUILDTAG)
	docker push $(DOCKER_REGISTRY)/$(IMAGE):$(BUILDTAG)

imagerun:
	docker build -t $(IMAGE) .
	docker run -it $(IMAGE) /bin/bash


export IMAGEURL:=$(DOCKER_REGISTRY)/$(IMAGE):$(BUILDTAG)

cloud-tools-deploy: image
	../cloud-tools-deploy.sh

cloud-tools-destroy:
	-../cloud-tools-deploy.sh -d

.PHONY: all clean distclean install image imagerun sh cloud-tools-deploy cloud-tools-destroy
