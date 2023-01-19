#!/bin/bash
set -euo pipefail
IFS=$' \n\t'

IDENTIFIER="cloud-tools-`uname -n|tr A-Z a-z|tr -dc a-z0-9`-`id -un|tr A-Z a-z|tr -dc a-z0-9`"
[ -z "${NAMESPACE:-}" ] && NAMESPACE="default"

INDIR=""
[ -d "in/" ] && INDIR="in/"

OUTDIR=""
[ -d "out/" ] && OUTDIR="out/"

[ -z "${PROXYCMD:-}" ] && PROXYCMD=' ["/usr/bin/microsocks"]'
SCRIPT=''

usage ()
{
 echo "usage: $0 [OPTS] [ARGS]"
 sed -n 's/^   \(.\))#\(.*\)$/ -\1 \2/p' < $0
 echo
 echo "The following environment variables should be set when using kafka-client.py:"
 echo "- KAFKA_CLIENT_BOOTSTRAP"
 echo "- KAFKA_CLIENT_USERNAME"
 echo "- KAFKA_CLIENT_PASSWORD"
 echo "- KAFKA_CLIENT_INSECURE"
 echo
}

OP="deploy"
while getopts dfpse:i:o:n:h opt; do
 case "$opt" in
   d)#  Destroy deployment
      OP="destroy"
      ;;
   f)#  Run only port-forwarding to proxy
      OP="forward"
      ;;
   p)#  Run http(s) proxy as proxy
      PROXYCMD=' ["/usr/bin/tinyproxy","-d","-c","/app/tinyproxy.conf"]'
      ;;
   s)#  Run socks5 server as proxy
      PROXYCMD=' ["/usr/bin/microsocks"]'
      ;;
   i)#DIR  Upload directory DIR to /data/, before executing the pod shell (default 'in/', if existing)
      INDIR="$OPTARG"
      ;;
   e)#SCRIPT  Execute given shell script
      PROXYCMD=''
      SCRIPT="$OPTARG"
      OP="script"
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


if [ "$OP" = "destroy" ]; then
 kubectl --namespace $NAMESPACE delete job/$IDENTIFIER || true
 exit 0
fi


(
 cat <<__X__
apiVersion: batch/v1
kind: Job
metadata:
  name: $IDENTIFIER
spec:
  activeDeadlineSeconds: 57600
  ttlSecondsAfterFinished: 600
  template:
    spec:
      restartPolicy: Never
      volumes:
        - name: data
          emptyDir:
            sizeLimit: 1Gi
      containers:
      - image: ${IMAGEURL:-ghcr.io/matgoebl/cloud-tools:latest}
        name: $IDENTIFIER
        resources:
          requests:
            cpu: "1m"
            memory: "1Mi"
            ephemeral-storage: "1Gi"
          limits:
            cpu: "1000m"
            memory: "256Mi"
            ephemeral-storage: "2Gi"
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
        - name: KAFKA_CLIENT_INSECURE
          value: "${KAFKA_CLIENT_INSECURE:-false}"
        - name: AWS_DEFAULT_REGION
          value: "${AWS_DEFAULT_REGION:-}"
        - name: AWS_ACCESS_KEY_ID
          value: "${AWS_ACCESS_KEY_ID:-}"
        - name: AWS_SECRET_ACCESS_KEY
          value: "${AWS_SECRET_ACCESS_KEY:-}"
        volumeMounts:
        - name: data
          mountPath: "/data"
        command:$PROXYCMD
__X__
 if [ -n "$SCRIPT" ]; then
  (
   echo '        - /bin/bash'
   echo '        - -c'
   echo '        - |'
   sed -e 's/^/          /' < "$SCRIPT"
  )
 fi
) | kubectl --namespace $NAMESPACE apply -f -



echo -n "Waiting for pod '$IDENTIFIER': "
pod=""
while [ -z "$pod" ]; do
 echo -n .
 sleep 1
 read namespace pod < <( kubectl get pods --all-namespaces --sort-by=.metadata.creationTimestamp | sed -ne 's/^\('"$NAMESPACE"'\)  *\('"$IDENTIFIER"'[^ ]*\) .*Running.*$/\1 \2/p' | tail -n 1; echo)
done
echo

if [ "$OP" = "forward" ]; then
 kubectl --namespace $NAMESPACE port-forward --address 127.0.0.1 $pod 1080:1080
 exit 0
fi

if [ "$OP" = "script" ]; then
 kubectl --namespace $NAMESPACE logs -f $pod
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
