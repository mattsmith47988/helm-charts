
minikube addons enable ingress

helm repo add jetstack https://charts.jetstack.io
helm upgrade --install cert-manager jetstack/cert-manager --namespace cluster-tools --create-namespace --set installCRDs=true

kubectl -n cluster-tools apply -f letsencrypt-prod.yaml