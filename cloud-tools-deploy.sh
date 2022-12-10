#!/bin/bash
set -euo pipefail
IFS=$' \n\t'

DEPLOYMENTNAME="cloud-tools-`uname -n|tr A-Z a-z|tr -dc a-z0-9`-`id -un|tr A-Z a-z|tr -dc a-z0-9`"
NAMESPACE="default"

INDIR=""
[ -d "in/" ] && INDIR="in/"

OUTDIR=""
[ -d "out/" ] && OUTDIR="out/"

usage ()
{
 echo "usage: $0 [OPTS] [ARGS]"
 sed -n 's/^   \(.\))#\(.*\)$/ -\1 \2/p' < $0
 echo
 echo "The following environment variables should be set when using kafka-client.py:"
 echo "- KAFKA_CLIENT_BOOTSTRAP"
 echo "- KAFKA_CLIENT_USERNAME"
 echo "- KAFKA_CLIENT_PASSWORD"
 echo
}

OP="deploy"
while getopts dfi:o:n:h opt; do
 case "$opt" in
   d)#  Delete deployment
      OP="delete"
      ;;
   f)#  Run only port-forwarding to socks5 server
      OP="forward"
      ;;
   i)#DIR  Upload directory DIR to /data/, before executing the pod shell (default 'in/', if existing)
      INDIR="$OPTARG"
      ;;
   o)#DIR  Download /data/out/ to directory DIR, after executing the pod shell (default 'out/', if existing)
      OUTDIR="$OPTARG"
      mkdir -p "$OUTDIR"
      ;;
   n)#NAMESPACE  Set namespace (default is 'default')
      NAMESPACE="$OPTARG"
      ;;
   h)#  Show help
      usage; exit 0 ;;
   *) usage; exit 1 ;;
 esac
done

shift $(($OPTIND - 1))


if [ "$OP" = "delete" ]; then
 kubectl --namespace $NAMESPACE delete deployments $DEPLOYMENTNAME || true
 exit 0
fi


kubectl --namespace $NAMESPACE apply -f - <<__X__
apiVersion: batch/v1
kind: Job
metadata:
  name: $DEPLOYMENTNAME
spec:
  activeDeadlineSeconds: 57600
  ttlSecondsAfterFinished: 600
  template:
    spec:
      restartPolicy: Never
      containers:
      - image: ${IMAGEURL:-ghcr.io/matgoebl/cloud-tools:latest}
        name: $DEPLOYMENTNAME
        resources:
          requests:
            cpu: "1m"
            memory: "1Mi"
            ephemeral-storage: "1Gi"
          limits:
            cpu: "1000m"
            memory: "256Mi"
            ephemeral-storage: "2Gi"
        command: [ "/usr/bin/microsocks"]
        lifecycle:
          postStart:
            exec:
              command: ["mkdir", "-p", "/data/in", "/data/out"]
        env:
        - name: KAFKA_CLIENT_BOOTSTRAP
          value: "${KAFKA_CLIENT_BOOTSTRAP:-}"
        - name: KAFKA_CLIENT_USERNAME
          value: "${KAFKA_CLIENT_USERNAME:-}"
        - name: KAFKA_CLIENT_PASSWORD
          value: "${KAFKA_CLIENT_PASSWORD:-}"
        volumeMounts:
        - name: data
          mountPath: "/data"
      volumes:
        - name: data
          emptyDir:
            sizeLimit: 1Gi
__X__


echo -n "Waiting for pod '$DEPLOYMENTNAME': "
pod=""
while [ -z "$pod" ]; do
 echo -n .
 sleep 1
 read namespace pod < <( kubectl get pods --all-namespaces --sort-by=.metadata.creationTimestamp | sed -ne 's/^\('"$NAMESPACE"'\)  *\('"$DEPLOYMENTNAME"'[^ ]*\) .*Running.*$/\1 \2/p' | tail -n 1; echo)
done
echo

if [ "$OP" = "forward" ]; then
 kubectl --namespace $NAMESPACE port-forward --address 127.0.0.1 $pod 1080:1080
 exit 0
fi

if [ -n "$INDIR" ]; then
 echo "Uploading $INDIR ..."
 kubectl --namespace "$namespace" cp "$INDIR" "$pod:/data/"
fi

echo "Connecting to $namespace:$pod ..."
echo

[ "$#" != "0" ] && CMD="-c"
kubectl --namespace "$namespace" exec -it "$pod" -- /bin/bash ${CMD:-} "$@" || true

if [ -n "$OUTDIR" ]; then
 echo "Downloading $OUTDIR ..."
 kubectl --namespace "$namespace" cp "$pod:/data/out/" "$OUTDIR"
fi
