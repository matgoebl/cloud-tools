ARG KAFKA_VERSION=2.13-3.7.0

FROM docker.io/python:3.11-bookworm AS builder
ARG KAFKA_VERSION
RUN python3 -m pip install pipenv
ENV PIPENV_VENV_IN_PROJECT=1
ADD Pipfile.lock Pipfile /app/
WORKDIR /app
RUN pipenv sync
RUN cd .venv/ && wget --continue https://repo1.maven.org/maven2/org/apache/avro/avro-tools/1.11.3/avro-tools-1.11.3.jar
RUN cd .venv/bin/ && wget --continue https://raw.githubusercontent.com/cykerway/complete-alias/1.18.0/complete_alias
RUN curl -O https://archive.apache.org/dist/kafka/3.7.0/kafka_$KAFKA_VERSION.tgz && tar -xzf kafka_$KAFKA_VERSION.tgz

FROM docker.io/python:3.11-bookworm
ARG KAFKA_VERSION
RUN apt-get update && apt-get -y upgrade
RUN apt install -y curl jq less joe hexcurse xxd pigz make iputils-ping traceroute mtr netcat-traditional socat nmap strace dnsutils openssl redir iproute2 kubernetes-client microsocks tinyproxy default-jre-headless kafkacat bash-completion vim nano bc
RUN mkdir awscli && cd awscli && curl https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o awscliv2.zip && unzip awscliv2.zip && ./aws/install && cd .. && rm -rf awscli

RUN echo "deb http://repo.mongodb.org/apt/debian bookworm/mongodb-org/8.0 main" > /etc/apt/sources.list.d/mongodb-org-8.0.list && \
    curl -sSL https://www.mongodb.org/static/pgp/server-8.0.asc | apt-key add - && \
    apt update && apt install -y mongodb-atlas-cli

RUN addgroup --gid 10001 user && adduser --uid 10001 --gid 10001 --home /app --no-create-home --disabled-password --gecos User --shell /bin/sh user
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
