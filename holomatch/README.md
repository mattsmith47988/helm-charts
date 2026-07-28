# holomatch

A Kubernetes chart for a containerized Star Trek: Voyager Elite Force
(Lilium Voyager / Quake 3 engine) **Holomatch** dedicated server. Map rotation,
bots, and match rules are defined in Helm values and rendered into the server's
`hm.cfg`.

```
helm repo add mattsmith47988 https://mattsmith47988.github.io/helm-charts/
helm repo update
```

```
helm install holomatch mattsmith47988/holomatch
```

## Exposing the server

`service.type` defaults to `ClusterIP`. To let players on the internet connect,
either enable the Gateway API `UDPRoute` (Envoy Gateway) or use a NodePort:

```
# Envoy Gateway (attaches to a Gateway with a UDP "game" listener):
helm upgrade --install holomatch mattsmith47988/holomatch \
  --set udpRoute.enabled=true

# ...or a standalone Gateway created by this chart:
helm upgrade --install holomatch mattsmith47988/holomatch \
  --set udpRoute.enabled=true --set udpRoute.gateway.create=true
```

Editing anything under `holomatch.*` (maps, bots, rules) and running
`helm upgrade` restarts the server automatically (a config checksum is tracked).

## Admin console

An optional sidecar serves a small, password-protected web page for running
live server commands (skip to next map, add/remove bots, kick, status, ...). It
relays commands to the server over Quake 3 **RCON** on localhost, so it needs
`holomatch.rconpassword` set (it is by default). The sidecar runs the bundled
[`files/rcon-console.py`](files/rcon-console.py) script on a stock Python image —
there is no extra image to build.

```
helm upgrade --install holomatch mattsmith47988/holomatch \
  --set console.enabled=true \
  --set console.host=holomatch-admin.example.com \
  --set console.auth.username=admin \
  --set console.auth.password='choose-a-strong-password'   # or omit to auto-generate
```

Then browse to `https://<console.host>`, sign in, type a command, and confirm
the dialog. Useful commands:

| Action | Command |
| --- | --- |
| Skip to next map in rotation | `vstr nextmap` |
| Load a specific map now | `map HM_BORG3` |
| Add a bot (name, skill 1–5) | `addbot tuvok 4` |
| Remove all bots | `kick allbots` |
| List connected players | `status` |
| Restart the current match | `map_restart` |

If you left `console.auth.password` blank, read the generated one with:

```
kubectl get secret <release>-holomatch-console-auth \
  -o jsonpath='{.data.password}' | base64 -d; echo
```

**Fallback (no browser):** the original `screen`-based console is still there —
`kubectl exec -it deploy/<release>-holomatch -c holomatch -- /console.sh`.

The console is served through Envoy Gateway (`HTTPRoute`) on its own hostname,
separate from the public game port. Keep `console.host` private and always set a
strong password — RCON can change many server settings.
