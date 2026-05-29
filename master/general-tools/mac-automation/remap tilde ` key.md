---
contexts:
  - "02-personal-brand"
type: "learning-note"
---

# remap tilde ` key

currently mac has login script at this location…

[https://apple.stackexchange.com/questions/281405/easy-way-to-remap-non-modifier-keys-on-mac](https://apple.stackexchange.com/questions/281405/easy-way-to-remap-non-modifier-keys-on-mac)

emapping `§ to `` and `± to ~` worked on my Mac (running OS X 10.15.6) without additional software with the following code snippet.

```
hidutil property --set '{"UserKeyMapping":
    [
     {"HIDKeyboardModifierMappingSrc":0x700000064,
      "HIDKeyboardModifierMappingDst":0x700000035}]
}'

```

To do this automatically at startup - Create a new file named `~/Library/LaunchAgents/com.user.loginscript.plist`

with the following content:

```
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.loginscript</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/hidutil</string>
        <string>property</string>
        <string>--set</string>
        <string>{"UserKeyMapping":[{"HIDKeyboardModifierMappingSrc":0x700000064, "HIDKeyboardModifierMappingDst":0x700000035}]}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>

```

The file needs to be registered with a one-off execution of the following command:

first: unload if already registered 

launchctl bootout gui/501 ~/Library/LaunchAgents/com.user.loginscript.plist

```
launchctl load ~/Library/LaunchAgents/com.user.loginscript.plist
```