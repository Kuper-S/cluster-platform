#!/bin/bash

NAMESPACE=$1
HOSTNAME="client.example.com"
IP_ADDRESS="192.168.49.2"

# Check if the entry already exists in /etc/hosts
if grep -q "$HOSTNAME" /etc/hosts; then
    echo "Entry for $HOSTNAME already exists in /etc/hosts"
else
    echo "$MINIKUBE_IP $HOSTNAME" | sudo tee -a /etc/hosts
    echo "Added $HOSTNAME to /etc/hosts"
fi
