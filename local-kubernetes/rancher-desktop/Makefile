# ============================================================================================
# Validator-manager Quick Deploy Makefile for Development and Testing
# ============================================================================================

KUBERNETES_CONTEXT = "rancher-desktop"
CHAIN_NAMESPACE="rococo"
HELM_CHART_DIR="../../helm/testnet-manager"

# ============================================================================================

all: lint kube check build install

# ============================================================================================

lint:
	@helm lint ${HELM_CHART_DIR}

kube:
	@rancher-desktop

check:
	@kubectl config use-context ${KUBERNETES_CONTEXT}
	@kubectl --context ${KUBERNETES_CONTEXT} get nodes

setup:
	@kubectl --context ${KUBERNETES_CONTEXT} apply -f ./kube-setup -f ../kube-setup

build: check
	cd ../../. && nerdctl -n k8s.io image build -t local/testnet-manager:latest .

reload: build install web
	@kubectl delete pods -n testnet-manager --all

reset:
	@helmfile --file ../charts/helmfile.yaml destroy
	@kubectl delete --all pvc -n rococo --all && kubectl delete --all pod -n rococo --all

apply:
	@helmfile --file ../charts/helmfile.yaml apply
# ============================================================================================

rpc:
	@xdg-open 'https://polkadot.js.org/apps/?rpc=ws%3A%2F%2F127.0.0.1%3A9944#/explorer'
	@kubectl port-forward service/localrococo-validator-alice-node 9944:9944 -n ${CHAIN_NAMESPACE}

para-shell:
	@xdg-open 'https://polkadot.js.org/apps/?rpc=ws%3A%2F%2F127.0.0.1%3A9948#/explorer'
	@kubectl port-forward service/localrococo-shell-collator-node 9948:9944 -n ${CHAIN_NAMESPACE}

para-moon:
	@xdg-open 'https://polkadot.js.org/apps/?rpc=ws%3A%2F%2F127.0.0.1%3A9949#/explorer'
	@kubectl port-forward service/localrococo-moonbase-collator-node 9949:9944 -n ${CHAIN_NAMESPACE}

para-mint:
	@xdg-open 'https://polkadot.js.org/apps/?rpc=ws%3A%2F%2F127.0.0.1%3A9950#/explorer'
	@kubectl port-forward service/localrococo-statemint-alice-node 9950:9944 -n ${CHAIN_NAMESPACE}

web:
	@xdg-open 'http://localhost:8080/'
	@kubectl port-forward service/testnet-manager 8080:80 -n ${CHAIN_NAMESPACE}

web-tasks:
	@xdg-open 'http://localhost:8081/tasks'
	@kubectl port-forward service/testnet-manager-task-scheduler 8081:80 -n ${CHAIN_NAMESPACE}

# ============================================================================================

install: build setup
	@helmfile --file ../charts/helmfile.yaml apply
	@kubectl delete --all pods -n testnet-manager # force recreate testnet-manager pod

# ============================================================================================

uninstall: check
	@helmfile --file ../charts/helmfile.yaml delete
	@kubectl --context ${KUBERNETES_CONTEXT} delete -n ${CHAIN_NAMESPACE} pvc --all

cleanup: check
	@kubectl --context ${KUBERNETES_CONTEXT} delete namespace ${CHAIN_NAMESPACE}
	@kubectl --context ${KUBERNETES_CONTEXT} delete namespace ${CHAIN_NAMESPACE}

# not implemented for rancher
# destroy:
# 	@minikube delete