import os
import subprocess
import requests
from flask import Flask, render_template, request, jsonify
from kubernetes import client, config
from kubernetes.client.exceptions import ApiException
from dotenv import load_dotenv
import yaml
import shutil

app = Flask(__name__)

# Load environment variables
load_dotenv()

GITHUB_USERNAME = os.getenv('GITHUB_USERNAME')
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
HELM_REPO_URL = "https://github.com/Kuper-S/helm-ShopApp"

k8s_available = False

# Load Kubernetes configuration
def load_kube_config():
    global k8s_available
    try:
        config.load_kube_config()
        k8s_available = True
    except Exception as e:
        print(f"Warning: Could not load Kubernetes config: {e}")
        k8s_available = False

load_kube_config()

def check_minikube():
    try:
        result = subprocess.run(["minikube", "status"], check=True, capture_output=True, text=True)
        print(f"Minikube status: {result.stdout}")
        return "Running" in result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error checking Minikube status: {e}")
        return False

def clone_helm_repo(repo_url, dest_dir):
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir)
    result = subprocess.run(f"git clone {repo_url} {dest_dir}", shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        raise Exception(f"Failed to clone repository: {result.stderr}")

def update_helm_values(values_file_path, api_image, client_image, namespace):
    with open(values_file_path, 'r') as file:
        values = yaml.safe_load(file)

    values['apiServer']['image']['repository'] = api_image.split(':')[0]
    values['apiServer']['image']['tag'] = api_image.split(':')[1]
    values['clientServer']['image']['repository'] = client_image.split(':')[0]
    values['clientServer']['image']['tag'] = client_image.split(':')[1]

    # Ensure ingress structure exists
    if 'ingress' not in values['clientServer']:
        values['clientServer']['ingress'] = {}

    values['clientServer']['ingress']['host'] = "client.example.com"
    values['clientServer']['ingress']['namespace'] = namespace

    with open(values_file_path, 'w') as file:
        yaml.safe_dump(values, file)

def update_hosts_file(namespace):
    script_path = os.path.join(os.path.dirname(__file__), 'update_hosts.sh')
    result = subprocess.run([script_path, namespace], check=True)
    if result.returncode != 0:
        raise Exception(f"Failed to update /etc/hosts: {result.stderr}")

def copy_secret_to_namespace(namespace):
    script_path = os.path.join(os.path.dirname(__file__), 'copy_secret.sh')
    result = subprocess.run([script_path, namespace], check=True)
    if result.returncode != 0:
        raise Exception(f"Failed to copy secret to namespace: {result.stderr}")

def get_github_images():
    headers = {
        'Authorization': f'token {GITHUB_TOKEN}',
        'Accept': 'application/vnd.github.v3+json'
    }
    url = f'https://api.github.com/users/{GITHUB_USERNAME}/packages?package_type=container'
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        packages = response.json()
        images = []
        for package in packages:
            if package['package_type'] == 'container':
                image_name = f"ghcr.io/{GITHUB_USERNAME}/{package['name']}:latest"
                images.append(image_name)
        return images
    else:
        return []

@app.route('/get_images')
def get_images():
    images = get_github_images()
    return jsonify(images)

@app.route('/')
def index():
    return render_template('index.html', k8s_available=k8s_available)

@app.route('/deploy', methods=['POST'])
def deploy():
    if not check_minikube():
        return jsonify({"error": "Minikube is not running"}), 503

    api_image = request.json.get('api_image')
    client_image = request.json.get('client_image')
    namespace = request.json.get('namespace')

    v1 = client.CoreV1Api()

    # Create the namespace
    try:
        namespace_body = client.V1Namespace(metadata=client.V1ObjectMeta(name=namespace))
        v1.create_namespace(body=namespace_body)
    except ApiException as e:
        if e.status != 409:  # Ignore "Already Exists" error
            return jsonify({"error": f"An error occurred: {e.reason}"}), e.status

    # Copy the mongo-secret to the new namespace
    copy_secret_to_namespace(namespace)

    # Clone the Helm chart repository
    helm_repo_dir = '/tmp/helm-ShopApp'
    clone_helm_repo(HELM_REPO_URL, helm_repo_dir)

    # Update the Helm values file
    values_file_path = os.path.join(helm_repo_dir, 'Shop-Helm', 'values.yaml')
    update_helm_values(values_file_path, api_image, client_image, namespace)

    # Update the /etc/hosts file
    update_hosts_file(namespace)

    # Install the Helm chart
    helm_chart_path = os.path.join(helm_repo_dir, 'Shop-Helm')
    helm_install_command = f"helm upgrade --install custom-app {helm_chart_path} --namespace {namespace}"
    result = subprocess.run(helm_install_command, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        return jsonify({"status": "Deployment created successfully"})
    else:
        return jsonify({"error": result.stderr}), 500

@app.route('/delete', methods=['POST'])
def delete():
    if not check_minikube():
        return jsonify({"error": "Minikube is not running"}), 503

    namespace = request.json.get('namespace')
    helm_uninstall_command = f"helm uninstall custom-app --namespace {namespace}"
    result = subprocess.run(helm_uninstall_command, shell=True, capture_output=True, text=True)

    if result.returncode != 0:
        return jsonify({"error": result.stderr}), 500

    v1 = client.CoreV1Api()
    try:
        v1.delete_namespace(name=namespace, body=client.V1DeleteOptions())
    except ApiException as e:
        if e.status != 404:
            return jsonify({"error": f"An error occurred: {e.reason}"}), e.status

    return jsonify({"status": "Deployment and namespace deleted successfully"})

@app.route('/status', methods=['GET'])
def status():
    if not check_minikube():
        return jsonify({"error": "Minikube is not running"}), 503

    namespace = request.args.get('namespace')
    v1 = client.CoreV1Api()

    try:
        pods = v1.list_namespaced_pod(namespace=namespace)
        pod_status = [{'name': pod.metadata.name, 'status': pod.status.phase} for pod in pods.items]
        return jsonify(pod_status)
    except ApiException as e:
        if e.status == 404:
            return jsonify({'error': f"Namespace '{namespace}' not found"}), 404
        else:
            return jsonify({'error': f"An error occurred: {e.reason}"}), e.status

@app.route('/cluster_info', methods=['GET'])
def cluster_info():
    v1 = client.CoreV1Api()

    nodes = v1.list_node()
    node_info = [{'name': node.metadata.name, 'status': node.status.conditions[-1].type} for node in nodes.items]

    namespaces = v1.list_namespace()
    namespace_info = [{'name': ns.metadata.name} for ns in namespaces.items]

    return jsonify({
        'nodes': node_info,
        'namespaces': namespace_info
    })

if __name__ == '__main__':
    app.run(debug=True)
