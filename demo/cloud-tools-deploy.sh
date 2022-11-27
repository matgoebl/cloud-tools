#!/bin/bash
set -euo pipefail
IFS=$' \n\t'

podname="cloud-tools-`uname -n`-`id -un`"
if [ "${1:-}" = "-d" ]; then
 kubectl delete deployments $podname
 exit 0
fi

kubectl apply -f - <<__X__
apiVersion: apps/v1
kind: Deployment
metadata:
  name: $podname
  labels:
    app: $podname
spec:
  replicas: 1
  selector:
    matchLabels:
      app: $podname
  template:
    metadata:
      labels:
        app: $podname
    spec:
      containers:
      - image: $IMAGEURL
        name: $podname
        command: [ "/bin/sleep", "999999d"]
        env:
        - name: KAFKA_CLIENT_BOOTSTRAP
          value: "my-cluster-kafka-0.$KAFKA_SERVICE.$NAMESPACE.svc:9093"
        - name: KAFKA_CLIENT_INSECURE
          value: "$KAFKA_CLIENT_INSECURE"
        - name: KAFKA_CLIENT_USERNAME
          value: "$KAFKA_CLIENT_USERNAME"
        - name: KAFKA_CLIENT_PASSWORD
          value: "$KAFKA_CLIENT_PASSWORD"
__X__

_kubectl_search_pod() {(
 search="$1"
 read namespace pod < <( kubectl get pods --all-namespaces --sort-by=.metadata.creationTimestamp | sed -ne 's/^\([^ ]*\)  *\('"$search"'[^ ]*\) .*$/\1 \2/p' | tail -n 1 )
 if [ -z "$pod" ]; then
  echo "error: $search not found" >&2
  exit 1
 else
  echo "$namespace $pod"
 fi
)}

_kubectl_pod_shell() {(
 search="$1"; shift
 read namespace pod < <( _kubectl_search_pod "$search" )
 if [ -n "$pod" ]; then
  echo "@ $namespace:$pod"
  kubectl --namespace "$namespace" exec -it "$pod" -- /bin/sh "$@"
 fi
)}

_kubectl_pod_shell "$podname" -c /bin/bash
