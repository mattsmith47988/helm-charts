{{/*
Expand the name of the chart.
*/}}
{{- define "holomatch-broker.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "holomatch-broker.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "holomatch-broker.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "holomatch-broker.labels" -}}
helm.sh/chart: {{ include "holomatch-broker.chart" . }}
{{ include "holomatch-broker.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "holomatch-broker.selectorLabels" -}}
app.kubernetes.io/name: {{ include "holomatch-broker.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Name of the coturn resources.
*/}}
{{- define "holomatch-broker.coturn.fullname" -}}
{{- printf "%s-coturn" (include "holomatch-broker.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Service account name.
*/}}
{{- define "holomatch-broker.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "holomatch-broker.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Name of the TURN shared-secret Secret (existing or chart-managed).
*/}}
{{- define "holomatch-broker.turnSecretName" -}}
{{- if .Values.turn.existingSecret }}
{{- .Values.turn.existingSecret }}
{{- else }}
{{- printf "%s-turn" (include "holomatch-broker.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Resolve the dedicated game-server host (defaults to the in-cluster Service).
*/}}
{{- define "holomatch-broker.gameServerHost" -}}
{{- if .Values.gameServer.host }}
{{- .Values.gameServer.host }}
{{- else }}
{{- printf "holomatch.%s.svc.cluster.local" .Release.Namespace }}
{{- end }}
{{- end }}
