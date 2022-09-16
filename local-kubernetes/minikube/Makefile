# ============================================================================================
# Validator-manager Quick Deploy Makefile for Development and Testing
# ============================================================================================

KUBERNETES_CONTEXT = "minikube"
CHAIN_NAMESPACE="rococo"
HELM_CHART_DIR="../../helm/testnet-manager"

# ============================================================================================

all: lint minikube check build install dash

# ============================================================================================

lint:
	@helm lint ${HELM_CHART_DIR}

minikube:
	@minikube start \
		--addons ingress --addons metrics-server --addons registry --driver docker \
		--kubernetes-version=1.23.3 --memory=8g --cpus=4

minikube-podman:
	@minikube start \
		--addons ingress --addons metrics-server --addons registry --driver podman \
		--container-runtime=containerd --memory=8g --cpus=4

check:
	@kubectl config use-context ${KUBERNETES_CONTEXT}
	@kubectl --context ${KUBERNETES_CONTEXT} get nodes

setup:
	@kubectl --context ${KUBERNETES_CONTEXT} apply -f ../kube-setup

build: check
	cd ../../. && minikube image build . -t local/testnet-manager

reload: build install
	@kubectl delete pods -n testnet-manager --all
	@make web
reset:
	@kubectl delete --all pvc -n rococo --all && kubectl delete --all pod -n rococo --all
# ============================================================================================

dash:
	@minikube dashboard

rpc:
	@xdg-open 'https://polkadot.js.org/apps/?rpc=ws%3A%2F%2F127.0.0.1%3A9944#/explorer'
	@kubectl port-forward service/localrococo-validator-alice-node 9944:9944 -n ${CHAIN_NAMESPACE}

rpc-woc:
	@xdg-open 'https://polkadot.js.org/apps/?rpc=ws%3A%2F%2F127.0.0.1%3A9945#/explorer'
	@kubectl port-forward localwococo-bootnode-1-0 9945:9944 -n wococo

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

destroy:
	@minikube delete
