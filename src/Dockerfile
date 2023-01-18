ARG KAFKA_VERSION=2.12-3.3.1

FROM docker.io/python:3.9-bullseye AS builder
ARG KAFKA_VERSION
RUN python3 -m pip install pipenv
ENV PIPENV_VENV_IN_PROJECT=1
ADD Pipfile.lock Pipfile /app/
WORKDIR /app
RUN pipenv sync
RUN curl -O https://downloads.apache.org/kafka/3.3.1/kafka_$KAFKA_VERSION.tgz && tar -xzf kafka_$KAFKA_VERSION.tgz

FROM docker.io/python:3.9-bullseye
ARG KAFKA_VERSION
RUN apt-get update && apt-get -y upgrade
RUN apt install -y curl jq less joe iputils-ping traceroute mtr netcat socat nmap strace dnsutils openssl redir iproute2 kubernetes-client microsocks tinyproxy default-jre-headless
RUN mkdir awscli && cd awscli && curl https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip -o awscliv2.zip && unzip awscliv2.zip && ./aws/install && cd .. && rm -rf awscli

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
