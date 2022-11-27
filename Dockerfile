FROM docker.io/python:3.9-slim-bullseye AS builder
RUN python3 -m pip install pipenv
ENV PIPENV_VENV_IN_PROJECT=1
ADD Pipfile.lock Pipfile /app/
WORKDIR /app
RUN pipenv sync

FROM docker.io/python:3.9-slim-bullseye AS runtime
ADD src/ /app/
ARG BUILDTAG=unknown
ENV BUILDTAG=${BUILDTAG}
RUN echo "${BUILDTAG}" > /app/.build
COPY --from=builder /app/.venv/ /app/.venv/
RUN adduser --uid 1000 --home /app --no-create-home --disabled-password --gecos User --shell /bin/sh user
WORKDIR /app/
USER user
CMD ["./entry.sh"]
