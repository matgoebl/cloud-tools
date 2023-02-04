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

export CLOUD_TOOLS_ARG=''

usage ()
{
 echo "usage: $0 [OPTS] [ARGS]"
 sed -n 's/^   \(.\))#\(.*\)$/ -\1 \2/p' < $0
 echo
 echo "The following environment variables should be set when using kafka-client.py:"
 echo "- CLOUD_TOOLS_KAFKA_CLIENT_BOOTSTRAP"
 echo "- CLOUD_TOOLS_KAFKA_CLIENT_USERNAME"
 echo "- CLOUD_TOOLS_KAFKA_CLIENT_PASSWORD"
 echo "- CLOUD_TOOLS_KAFKA_CLIENT_INSECURE"
 echo
 echo "A file cloud-settings.sh is sourced if found."
 echo
}

OP="deploy"
while getopts dfpsce:i:o:n:e:a:h opt; do
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
   c)#  Connect to a running instance, without deployment
      OP="connect"
      ;;
   o)#DIR  Download /data/out/ to directory DIR, after executing the pod shell (default 'out/', if existing)
      OUTDIR="$OPTARG"
      mkdir -p "$OUTDIR"
      ;;
   n)#NAMESPACE  Set namespace (default is 'default')
      NAMESPACE="$OPTARG"
      ;;
   a)#ARG  Set CLOUD_TOOLS_ARG (can be used in cloud-settings.sh and on target)
      CLOUD_TOOLS_ARG="$OPTARG"
      ;;
   h)#  Show help
      usage; exit 0 ;;
   *) usage; exit 1 ;;
 esac
done

shift $(($OPTIND - 1))


[ -e cloud-settings.sh ] && source cloud-settings.sh


if [ "$OP" = "destroy" ]; then
 kubectl --namespace $NAMESPACE delete job/$IDENTIFIER || true
 exit 0
fi


if [ "$OP" != "connect" ]; then
(
 cat <<__X__
apiVersion: batch/v1
kind: Job
metadata:
  name: $IDENTIFIER
spec:
  activeDeadlineSeconds: 43200
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
        volumeMounts:
        - name: data
          mountPath: "/data"
        env:
__X__

 for var in ${!CLOUD_TOOLS_*};do
  echo "        - name: ${var##CLOUD_TOOLS_}"
  echo "          value: \"${!var}\""
 done

 echo "        command:$PROXYCMD"
 if [ -n "$SCRIPT" ]; then
  (
   echo '        - /bin/bash'
   echo '        - -c'
   echo '        - |'
   sed -e 's/^/          /' < "$SCRIPT"
  )
 fi
) | kubectl --namespace $NAMESPACE apply -f -
fi


echo -n "Waiting for latest pod '$IDENTIFIER-*': "
pod=""
while [ -z "$pod" ]; do
 echo -n .
 sleep 1
 read namespace pod < <( kubectl get pods --all-namespaces --sort-by=.metadata.creationTimestamp | sed -ne 's/^\('"$NAMESPACE"'\)  *\('"$IDENTIFIER-"'[^ ]*\) .*Running.*$/\1 \2/p' | tail -n 1; echo)
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
