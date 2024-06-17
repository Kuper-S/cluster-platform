#!/bin/bash

SOURCE_NAMESPACE="default"
TARGET_NAMESPACE="$1"
SECRET_NAME="mongo-secret"

# Get the secret from the source namespace and apply it to the target namespace
kubectl get secret $SECRET_NAME -n $SOURCE_NAMESPACE -o yaml | \
    sed "s/namespace: $SOURCE_NAMESPACE/namespace: $TARGET_NAMESPACE/" | \
    kubectl apply -n $TARGET_NAMESPACE -f -

