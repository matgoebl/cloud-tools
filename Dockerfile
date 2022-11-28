FROM docker.io/python:3.9-slim-bullseye AS builder
RUN python3 -m pip install pipenv
ENV PIPENV_VENV_IN_PROJECT=1
ADD Pipfile.lock Pipfile /app/
WORKDIR /app
RUN pipenv sync

FROM docker.io/python:3.9-bullseye
RUN apt-get update && apt-get -y upgrade
RUN apt install -y curl jq less joe traceroute mtr nmap strace dnsutils openssl redir iproute2

RUN adduser --uid 1000 --home /app --no-create-home --disabled-password --gecos User --shell /bin/sh user
COPY --from=builder /app/.venv/ /app/.venv/
ADD src/ /app/
COPY bashrc /app/.bashrc
ARG BUILDTAG=unknown
ENV BUILDTAG=${BUILDTAG}
RUN echo "${BUILDTAG}" > /app/.build
WORKDIR /app/
USER user
CMD ["./entry.sh"]
