ARG KAFKA_VERSION=2.13-3.3.2

FROM docker.io/python:3.9-bullseye AS builder
ARG KAFKA_VERSION
RUN python3 -m pip install pipenv
ENV PIPENV_VENV_IN_PROJECT=1
ADD Pipfile.lock Pipfile /app/
WORKDIR /app
RUN pipenv sync
RUN cd .venv/ && wget --continue https://repo1.maven.org/maven2/org/apache/avro/avro-tools/1.11.1/avro-tools-1.11.1.jar
RUN cd .venv/bin/ && wget --continue https://raw.githubusercontent.com/cykerway/complete-alias/1.18.0/complete_alias
RUN curl -O https://archive.apache.org/dist/kafka/3.3.2/kafka_$KAFKA_VERSION.tgz && tar -xzf kafka_$KAFKA_VERSION.tgz

FROM docker.io/python:3.9-bullseye
ARG KAFKA_VERSION
RUN apt-get update && apt-get -y upgrade
RUN apt install -y curl jq less joe hexcurse xxd pigz make iputils-ping traceroute mtr netcat socat nmap strace dnsutils openssl redir iproute2 kubernetes-client microsocks tinyproxy default-jre-headless kafkacat
RUN mkdir awscli && cd awscli && curl https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o awscliv2.zip && unzip awscliv2.zip && ./aws/install && cd .. && rm -rf awscli

RUN echo "deb http://repo.mongodb.org/apt/debian bullseye/mongodb-org/5.0 main" > /etc/apt/sources.list.d/mongodb-org-5.0.list && \
    curl -sSL https://www.mongodb.org/static/pgp/server-5.0.asc | apt-key add - && \
    apt update && apt install -y mongodb-org

RUN adduser --uid 1000 --home /app --no-create-home --disabled-password --gecos User --shell /bin/sh user
COPY --from=builder /app/.venv/ /app/.venv/
COPY --from=builder /app/kafka_$KAFKA_VERSION/ /app/kafka/
ADD . /app/
WORKDIR /app/
RUN mv bashrc .bashrc
ARG BUILDTAG=unknown
ENV BUILDTAG=${BUILDTAG}
RUN echo "${BUILDTAG}" > /app/.build
USER user
CMD ["./entry.sh"]
