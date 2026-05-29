# Per-app API redirect experiment

This folder is for experimenting with:

- an easy editable config for `myapp.app + https://api.lemonsqueezy.com -> localhost`
- a best-effort per-app launch path using proxy environment variables
- notes on what is required for true transparent interception on macOS

Important: the included runnable scripts do **not** satisfy the stronger requirement of "works for any macOS app always." macOS does not provide a simple open-source/Homebrew "per-host `/etc/hosts`, but scoped to one `.app` bundle" mechanism. A true always-on solution needs transparent network interception through `pf` or a Network Extension. `pf` can be made host-wide, but it cannot cleanly match one `.app` bundle for `rdr` redirects.

## Config

Edit:

```txt
$(vault root)/_master/general-tools/per-app-api-redirect/config.json
```

Current mapping:

```json
{
  "appPath": "/Applications/myapp.app",
  "target": {
    "scheme": "https",
    "host": "api.lemonsqueezy.com"
  },
  "local": {
    "scheme": "http",
    "host": "127.0.0.1",
    "port": 8081
  },
  "proxy": {
    "host": "127.0.0.1",
    "port": 8080
  }
}
```

## Requirements

```sh
brew install mitmproxy
```

`mitmproxy` is already installed on this Mac at the time this folder was created.

## Best-effort per-app mode

Run whatever you want to receive the redirected API traffic on localhost. The default in these scripts is:

```txt
http://127.0.0.1:8081
```

You can change that in `config.json`.

Start the proxy:

```sh
cd "$(vault root)/_master/general-tools/per-app-api-redirect"
./run_proxy.sh
```

Launch the app through that proxy in another terminal:

```sh
cd "$(vault root)/_master/general-tools/per-app-api-redirect"
./launch_myapp_with_proxy.sh
```

This launcher sets proxy environment variables only for that app process. Apps built on Electron, Node, Chromium, curl, or many common HTTP stacks often honor these. Some native or hardened macOS apps ignore proxy environment variables.

You can still override the app path for one run:

```sh
./launch_myapp_with_proxy.sh /Applications/SomeOther.app
```

## What the always-on version would require

For "works for any macOS app always," the routing cannot depend on proxy environment variables. The realistic choices are:

- **System-wide transparent routing:** use `pf` to redirect connections for Lemon Squeezy API IPs/port 443 to a local transparent proxy or local TLS service. This works regardless of the app, but it affects every app on the Mac, not just `myapp.app`.
- **Per-app Network Extension:** a custom or commercial Network Extension/per-app VPN style tool can classify traffic by app and route it. This is the proper per-app shape, but it is not a simple Homebrew script and usually involves Apple entitlements, a signed app, and/or commercial software.
- **Per-app proxy tools:** tools like Proxifier-style apps can do this, but the best-known options are generally commercial, not a plain open-source Homebrew package.

So the exact combination, "only `/Applications/myapp.app`, only `https://api.lemonsqueezy.com`, works for any app stack, open-source, Homebrew-installed," is the part that does not really exist as a normal macOS scripting setup.

## Current open-source candidates

- **mitmproxy:** mature, Homebrew-installable, scriptable, and config-friendly. Good for this folder, but per-app mode depends on the app honoring proxy settings.
- **Rockxy:** open-source native macOS proxy app with Homebrew cask install and Map Remote / Map Local features. It is closer to the "Mac app traffic debugger" shape, but it is a GUI app rather than this JSON-script workflow, and it still depends on macOS proxy/interception mechanics rather than a magic per-app hosts file.
- **LuLu:** reputable open-source per-app outbound firewall. It can identify apps and destinations, but it blocks/allows traffic; it does not rewrite `api.lemonsqueezy.com` to localhost.

## HTTPS certificate note

If the app calls `https://api.lemonsqueezy.com`, mitmproxy has to decrypt and re-issue TLS locally. The app must trust mitmproxy's certificate authority, otherwise requests will fail with certificate errors.

After running mitmproxy once, the CA certificate is usually here:

```txt
~/.mitmproxy/mitmproxy-ca-cert.pem
```

Install it into Keychain Access and set it to trusted for SSL. Some apps use certificate pinning, and those will still reject interception.
