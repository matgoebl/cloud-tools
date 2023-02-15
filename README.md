# cloud-tools
Some of my Cloud Tools, including kafka&kinesis sender/receiver and AVRO encoder/decoder.

(c) 2022 Copyright: Matthias Goebl  (e-mail: matthias dot goebl at goebl dot net)

Published under the Apache License 2.0.

For details see https://github.com/matgoebl/cloud-tools/

[![Create and Publish Docker Image to ghcr.io](https://github.com/matgoebl/cloud-tools/actions/workflows/publish.yml/badge.svg)](https://github.com/matgoebl/cloud-tools/actions/workflows/publish.yml)


## Quickstart

Deploy the latest cloud-tools container to your default cluster (check with `kubectl cluster-info`):

    ./cloud-tools-deploy.sh

After the container is deployed, you will get a shell on it. There you can issue commands, that work only within the cluster, e.g.

    $ dig +noall +answer kubernetes.default.svc.cluster.local
    kubernetes.default.svc.cluster.local. 5	IN A	10.43.0.1

    $ curl -ki https://kubernetes.default.svc.cluster.local
    HTTP/1.1 401 Unauthorized

(i.e. connectivity works, but we get an error 401 because we did not provide a token)  
The pod is deployed as job, that will be removed after 16 hours.  
To manually remove the pod use:

    ./cloud-tools-deploy.sh -d

Get help:

    $ ./cloud-tools-deploy.sh -h
    usage: ./cloud-tools-deploy.sh [OPTS] [ARGS]

    -d   Destroy deployment
    -f   Run only port-forwarding to proxy
    -p   Run http(s) proxy as proxy
    -s   Run socks5 server as proxy
    -i DIR  Upload directory DIR to /data/, before executing the pod shell (default 'in/', if existing)
    -e SCRIPT  Execute given shell script
    -c   Connect to a running instance, without deployment
    -o DIR  Download /data/out/ to directory DIR, after executing the pod shell (default 'out/', if existing)
    -n NAMESPACE  Set namespace (default is 'default')
    -a ARG  Set CLOUD_TOOLS_ARG (can be used in cloud-settings.sh and on target)
    -h   Show help

    The following environment variables should be set when using kafka-client.py:
    - CLOUD_TOOLS_KAFKA_CLIENT_BOOTSTRAP
    - CLOUD_TOOLS_KAFKA_CLIENT_USERNAME
    - CLOUD_TOOLS_KAFKA_CLIENT_PASSWORD
    - CLOUD_TOOLS_KAFKA_CLIENT_INSECURE

    A file cloud-settings.sh is sourced if it is found.


## Error '...field is immutable'

If you change the configuration of the deployment, you will get an error message like:

    The Job "cloud-tools-xxx-yyy" is invalid: ...: field is immutable

If this happens, just destroy the deploment first:

    ./cloud-tools-deploy.sh -d


## Using SOCKS5H for a local socks tunnel

Start the socks tunnel, it uses [MicroSocks](https://github.com/rofl0r/microsocks):

    ./cloud-tools-deploy.sh -f

On another terminal, local software can use the socks5 proxy, e.g.

    curl --proxy socks5h://127.0.0.1:1080 -ki https://kubernetes.default.svc.cluster.local

If an application does not provide socks support, you can try socksify (`apt install dante-client` in debian):

    export SOCKS5_SERVER=127.0.0.1:1080
    socksify curl -ki https://kubernetes.default.svc.cluster.local
 

## Using Tinyproxy for a local http tunnel

Start the http tunnel, it uses [Tinyproxy](https://tinyproxy.github.io):

    ./cloud-tools-deploy.sh -d
    ./cloud-tools-deploy.sh -f -p

On another terminal, local software can use the http(s) proxy, e.g.

    export https_proxy=http://127.0.0.1:1080
    export http_proxy=http://127.0.0.1:1080
    export no_proxy=mycluster.example.org,test.example.org
    curl -ki https://kubernetes.default.svc.cluster.local

If you still want ot reach your cluster with `kubectl`, add the API server to the `no_proxy` environment variable.


## Execute a Shell Script

You can upload, execute and watch the output of a shell script:

    echo 'while sleep 1;do date; done' > test.sh
    ./cloud-tools-deploy.sh -e test.sh


## Extensibility

- All local environment variables beginning with `CLOUD_TOOLS_` will be passed into the deployment with the prefix `CLOUD_TOOLS_` removed,
  e.g. `CLOUD_TOOLS_AWS_DEFAULT_REGION` will be passed as `AWS_DEFAULT_REGION`.
- If there is a local file `cloud-settings.sh`, it will be sourced. Its purpose is to set up CLOUD_TOOLS_* environment.
 - The option `-a` sets the environment variable CLOUD_TOOLS_ARG, that can be used in `cloud-settings.sh` and the deployment.
 - A file `./in/cloud.bashrc` will be uploaded (along with `./in/*`) and sourced after pod shell login.


## Passing AWS Credentials

For using AWS services in EKS you may use a service account that is annotated with an IAM role.

Alternatively just get AWS credentials for the role you want to assume in `cloud-settings.sh` like this:

    export $(printf "CLOUD_TOOLS_AWS_ACCESS_KEY_ID=%s CLOUD_TOOLS_AWS_SECRET_ACCESS_KEY=%s CLOUD_TOOLS_AWS_SESSION_TOKEN=%s" $(aws sts assume-role --profile some-profile --role-arn arn:aws:iam::123456789012:role/some_role --role-session-name CloudToolsSession --query "Credentials.[AccessKeyId,SecretAccessKey,SessionToken]" --output text))

    export CLOUD_TOOLS_AWS_DEFAULT_REGION=eu-central-1


## Kafka kafka send/receive and AVRO encode/decode on a pod

### Set server and credentials

First set and export the relevant kafka settings, e.g.:

    export KAFKA_CLIENT_BOOTSTRAP=my-cluster-kafka-0.kafka-service.default.svc:9093
    export KAFKA_CLIENT_USERNAME=myuser
    export KAFKA_CLIENT_PASSWORD=mypassword
    export KAFKA_CLIENT_INSECURE=true

or

    export KAFKA_CLIENT_PASSWORD=$(kubectl --namespace default get secret/mykafkaclient -o json | jq .data.password -r | base64 -d)

or

    export KAFKA_CLIENT_PASSWORD=$(aws secretsmanager --profile someprofile get-secret-value --secret-id mykafkaclient --no-cli-pager --output json | jq -r .SecretString)


### Shell into cluster

    ./cloud-tools-deploy.sh


### Getting help

    user@cloud-tools-myhost-myuser--abcd123:/data$ kafka-client.py --help
    Usage: kafka-client.py [OPTIONS] COMMAND [ARGS]...

    A simple kafka commandline client written in python. It sends and receives
    messages while optionally decoding them using plugins.

    Copyright (c) 2022 Matthias Goebl (matthias dot goebl at goebl dot net)

    Published under the Apache License Version 2.0

    For details see https://github.com/matgoebl/cloud-tools/

    Options:
    -b, --bootstrap TEXT   Kafka bootstrap server.  [default: localhost:9093]
    -v, --verbose
    -U, --username TEXT    Kafka username.
    -P, --password TEXT    Kafka password.
    -S, --insecure         Do not verfy SSL.
    -M, --dnsmap TEXT      Remap DNS names.
    -I, --pluginpath TEXT  Load encoder/decoder plugins from given path.
    --help                 Show this message and exit.

    Commands:
    list  List topics.
    recv  Receive messages.
    send  Send messages.


    user@cloud-tools-myhost-myuser--abcd123:/data$ kafka-client.py list --help
    Usage: kafka-client.py list [OPTIONS]

    List topics.

    Options:
    --help  Show this message and exit.


    user@cloud-tools-myhost-myuser--abcd123:/data$ kafka-client.py send --help
    Usage: kafka-client.py send [OPTIONS]

    Send messages.

    Options:
    -t, --topic TEXT            Topic to send to.  [required]
    -k, --key TEXT              Key to use for sending.
    -K, --keyfile FILENAME      Read key from file.
    -h, --headers TEXT          Header to set for every sent message, e.g.
                                abc:123;xyz:987
    -p, --payload TEXT          Payload to send.
    -H, --headersfile FILENAME  Read headers from file.
    -P, --payloadfile FILENAME  Read payload from file.
    -r, --rate INTEGER          Rate limit in requests per second (default:
                                almost no limit)
    -m, --multiline             Read keys and payloads line-by-line from their
                                files
    -c, --count INTEGER         Number of messages to send (ignored in multiline
                                mode).  [default: 1]
    --help                      Show this message and exit.


    user@cloud-tools-myhost-myuser--abcd123:/data$ kafka-client.py recv --help
    Usage: kafka-client.py recv [OPTIONS]

    Receive messages.

    Options:
    -t, --topic TEXT          Topic to receive from.  [required]
    -c, --count INTEGER       Number of messages to receive (will be rounded to
                                multiple of partitions).  [default: 1]
    -f, --follow              Wait for new messages.
    -j, --jump TEXT           Jump to given date and time, e.g. "2023-01-18
                                22:04:10". A single negative number will seek back
                                the given number of seconds, e.g. "-60" will start
                                a minute ago.
    -w, --writefilepath TEXT  Write messages (.data), headers (.header) and keys
                                (.key) to files named <topic>.<number> at the
                                given path (e.g. "."). The header may contain
                                string dumps, that cannot be transparently sent
                                again via "send" command.
    -k, --key TEXT            Filter for messages with the given key.
    -s, --searchpayload TEXT  Filter for message whose payload matches the given
                                regex.
    -S, --searchheader TEXT   Filter for message whose headers match the given
                                regex.
    -X, --extractheader TEXT  Extract and output the given header field for each
                                message.
    -q, --quiet               By quiet.
    --help                    Show this message and exit.


### Send kafka messages

    user@cloud-tools-myhost-myuser--abcd123:/data$ kafka-client.py send -t test -k somekey -h 'SomeHeader:123' -p '{"hello":"world!"}'


### Receive kafka messages

    user@cloud-tools-myhost-myuser--abcd123:/data$ kafka-client.py recv -t test
    2022-12-11T19:26:41.620000+00:00 test(0)1 [SomeHeader:123] b'somekey':b'{"hello":"world!"}'

Write messages to files:

    myhost$ mkdir out
    myhost$ ./cloud-tools-deploy.sh -o out

    user@cloud-tools-myhost-myuser--abcd123:/data$ cd out

    user@cloud-tools-myhost-myuser--abcd123:/data/out$ kafka-client.py recv -t test -w .
    2022-12-11T19:26:41.620000+00:00 test(0)1 [SomeHeader:123] b'somekey':b'{"hello":"world!"}'

    user@cloud-tools-myhost-myuser--abcd123:/data/out$ head -n999 test.00001.*
    ==> test.00001.data <==
    {"hello":"world!"}
    ==> test.00001.header <==
    SomeHeader:123

    ==> test.00001.key <==
    somekey

    user@cloud-tools-myhost-myuser--abcd123:/data/out$ exit
    exit
    Downloading out/ ...

The received messages are automatically downloaded to the host into out/.


### Decode avro messages


Get help:

    $ avro-tool.py --help
    Usage: avro-tool.py [OPTIONS] COMMAND [ARGS]...

    AVRO Message Encoder/Decoder written in python.

    Copyright (c) 2022 Matthias Goebl (matthias dot goebl at goebl dot net)

    Published under the Apache License Version 2.0

    For details see https://github.com/matgoebl/cloud-tools/

    Options:
    -s, --schema FILENAME  AVRO schema file to use (.avsc)  [required]
    -v, --verbose          Be more verbose, can be repeated (up to 3 times).
    --help                 Show this message and exit.

    Commands:
    dec   Decode an AVRO encoded payload to JSON.
    dump  Dump schema.
    enc   Encode JSON data to AVRO payload.


    $ avro-tool.py -s demo.avsc dump --help
    Usage: avro-tool.py dump [OPTIONS]

    Dump schema.

    Options:
    --help  Show this message and exit.


    $ avro-tool.py -s demo.avsc enc --help
    Usage: avro-tool.py enc [OPTIONS]

    Encode JSON data to AVRO payload.

    Options:
    -i, --input FILENAME   Input data file (.json)
    -o, --output FILENAME  Output AVRO payload file (.avro)  [required]
    --help                 Show this message and exit.


    $ avro-tool.py -s in/demo.avsc dec --help
    Usage: avro-tool.py dec [OPTIONS]

    Decode an AVRO encoded payload to JSON.

    Options:
    -i, --input FILENAME      Input AVRO file to decode (.avro)  [required]
    -h, --skipheader INTEGER  Skip given amount of initial header bytes
    -o, --output FILENAME     Output data file (.json)
    --help                    Show this message and exit.


Prepare local upload directory:

    $ mkdir in; cp demo.avsc demo.json in/

This directory is automatically uploaded to the pod into /data/.  

Encode and decode a test message:

    user@cloud-tools-myhost-myuser--abcd123:/data$ avro-tool.py -s in/demo.avsc enc -i in/demo.json -o demo.avro

    user@cloud-tools-myhost-myuser--abcd123:/data$ avro-tool.py -s in/demo.avsc dec -i demo.avro
    {
        "choice": "A",
        "count": 5,
        "hello": "World!",
        "numbers": [
            1,
            2,
            3
        ],
        "option": null
    }


## Using a locally built image

Set your own registry and build:

    export DOCKER_REGISTRY=myregistry.example.org:5000
    cd src && make cloud-tools-destroy image cloud-tools-deploy


## Run kafka demo

    $ cd demo; make all

As part of the demo a kafka broker is installed into your cluster, the kafka connection is forwarded to the local host, a test message is sent and received.

