# cloud-tools
Some of my Cloud Tools, including kafka sender/receiver and AVRO encoder/decoder.

(c) 2022 Copyright: Matthias Goebl  (e-mail: matthias dot goebl at goebl dot net)

Published under the Apache License 2.0.


## Quickstart

Deploy the latest tools container to your default cluster (`kubectl cluster-info`):

    ./cloud-tools-deploy.sh

After the container is deployed, you will get a shell on it. There you can issue commands, that work only within the cluster, e.g.

    $ dig +noall +answer kubernetes.default.svc.cluster.local
    kubernetes.default.svc.cluster.local. 5	IN A	10.43.0.1

    $ curl -ki https://kubernetes.default.svc.cluster.local
    HTTP/1.1 401 Unauthorized

(i.e. connectivity works, 401 because we did not provide a token)  
The pod is deployed as job, that will be removed after 16 hours.  
To manually remove the pod use:

    ./cloud-tools-deploy.sh -d

Get help:

    $ ./cloud-tools-deploy.sh -h
    usage: ./cloud-tools-deploy.sh [OPTS] [ARGS]
    -d   Destroy deployment
    -f   Run only port-forwarding to socks5 server
    -i DIR  Upload directory DIR to /data/, before executing the pod shell (default 'in/', if existing)
    -o DIR  Download /data/out/ to directory DIR, after executing the pod shell (default 'out/', if existing)
    -n NAMESPACE  Set namespace (default is 'default')
    -h   Show help

    The following environment variables should be set when using kafka-client.py:
    - KAFKA_CLIENT_BOOTSTRAP
    - KAFKA_CLIENT_USERNAME
    - KAFKA_CLIENT_PASSWORD
    - KAFKA_CLIENT_INSECURE


## Using SOCKS5H for a local tunnel

Start the tunnel:

    ./cloud-tools-deploy.sh -f

On another terminal, local software can use the tunnel, e.g.

    curl --proxy socks5://127.0.0.1:1080 -ki https://kubernetes.default.svc.cluster.local


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

    export KAFKA_CLIENT_PASSWORD=$(ws secretsmanager --profile someprofile get-secret-value --secret-id mykafkaclient --no-cli-pager --output json | jq -r .SecretString)


### Shell into cluster

    ./cloud-tools-deploy.sh


### Getting help

    user@cloud-tools-myhost-myuser--abcd123:/data$ kafka-client.py --help
    Usage: kafka-client.py [OPTIONS] COMMAND [ARGS]...

    Receive messages.

    Options:
    -b, --bootstrap TEXT  Kafka bootstrap server.  [default: localhost:9093]
    -v, --verbose
    -U, --username TEXT   Kafka username.
    -P, --password TEXT   Kafka password.
    -S, --insecure        Do not verfy SSL.
    -M, --dnsmap TEXT     Remap DNS names.
    --help                Show this message and exit.

    Commands:
    list  List topics.
    recv  Receive messages.
    send  Send message.


    user@cloud-tools-myhost-myuser--abcd123:/data$ kafka-client.py list --help
    Usage: kafka-client.py list [OPTIONS]

    List topics.

    Options:
    --help  Show this message and exit.


    user@cloud-tools-myhost-myuser--abcd123:/data$ kafka-client.py send --help
    Usage: kafka-client.py send [OPTIONS]

    Send message.

    Options:
    -t, --topic TEXT            Topic to send to.  [required]
    -k, --key TEXT              Key to use for sending.  [default: TEST]
    -h, --headers TEXT          Header to set for every sent message, e.g.
                                abc:123;xyz:987
    -p, --payload TEXT          Payload to send.  [default: abc123]
    -H, --headersfile FILENAME  Read headers from file.
    -P, --payloadfile FILENAME  Read payload from file.
    --help                      Show this message and exit.


    user@cloud-tools-myhost-myuser--abcd123:/data$ kafka-client.py recv --help
    Usage: kafka-client.py recv [OPTIONS]

    Receive messages.

    Options:
    -t, --topic TEXT          Topic to receive from.  [required]
    -c, --count INTEGER       Number of messages to receive (will be rounded to
                                multiple of partitions).  [default: 1]
    -f, --follow              Wait for new messages.
    -j, --jump TEXT           Jump to given date and time.
    -w, --writefile TEXT      Write messages (.data), headers (.header) and key
                                (.key) to files using the given pattern. "." is a
                                shortcut for <topic>.%05i
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
    2022-12-11T19:26:41.620000+00:00 test(0)1 [;SomeHeader:123;] b'somekey':b'{"hello":"world!"}'

Write messages to files:

    myhost$ mkdir out
    myhost$ ./cloud-tools-deploy.sh -o out

    user@cloud-tools-myhost-myuser--abcd123:/data$ cd out

    user@cloud-tools-myhost-myuser--abcd123:/data/out$ kafka-client.py recv -t test -w .
    2022-12-11T19:26:41.620000+00:00 test(0)1 [;SomeHeader:123;] b'somekey':b'{"hello":"world!"}'

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

    AVRO Message Encoder/Decoder.

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

