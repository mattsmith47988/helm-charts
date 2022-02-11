# helm-charts

Add this to your helm repos:

```
helm repo add mattsmith47988 https://mattsmith47988.github.io/helm-charts/
helm repo update
```

Updating the index:

```
helm repo index --url https://mattsmith47988.github.io/helm-charts/ --merge index.yaml .
```