---
contexts:
  - "personal-brand"
type: "learning-note"
---

# Mac OS / iPhone

## Remap tilde key

[remap tilde ` key](Mac%20OS%20iPhone/remap%20tilde%20%60%20key.md)

allow execute of script

```jsx
chmod 755 CreateOctopusRelease.sh
```

allow opening of files when quarantine is annoying af

```jsx
xattr -d com.apple.quarantine ./Linkedin\ Lead\ Magnet.md
```

flush DNS cache

```jsx

sudo dscacheutil -flushcache; sudo killall -HUP mDNSResponder
```

Remove autocorrect and completion kak

```jsx
defaults write NSGlobalDomain NSAutomaticSpellingCorrectionEnabled -bool false

defaults write NSGlobalDomain NSAutomaticTextCompletionEnabled -bool false

```

Refusing to mount hdd after unplugging

```
$ ps -ef | grep fsck
$ sudo kill [pid from above]
```

```jsx
//script to make dock animation better
defaults write com.apple.dock autohide-delay -int 0
defaults write com.apple.dock autohide-time-modifier -float 0.4
killall Dock

Mouse acceleration: defaults write .GlobalPreferences com.apple.mouse.scaling -1§

**************************************
Terminal commands (paste the entire string)
**************************************
𝗙𝗮𝘀𝘁𝗲𝗿 𝗗𝗼𝗰𝗸 𝗛𝗶𝗱𝗶𝗻𝗴: defaults write com.apple.dock autohide-delay -float 0; defaults write com.apple.dock autohide-time-modifier -int 0;killall Dock
𝗙𝗮𝘀𝘁𝗲𝗿 𝗗𝗼𝗰𝗸 𝗛𝗶𝗱𝗶𝗻𝗴 𝗨𝗻𝗱𝗼: defaults write com.apple.dock autohide-delay -float 0.5; defaults write com.apple.dock autohide-time-modifier -int 0.5 ;killall Dock

𝗔𝗱𝗱 𝗗𝗼𝗰𝗸 𝗦𝗽𝗮𝗰𝗲𝗿 (paste for each spacer): defaults write com.apple.dock persistent-apps -array-add '{tile-data={}; tile-type="spacer-tile";}' && killall Dock
𝗔𝗱𝗱 𝗛𝗮𝗹𝗳-𝗛𝗲𝗶𝗴𝗵𝘁 𝗗𝗼𝗰𝗸 𝗦𝗽𝗮𝗰𝗲𝗿 (paste for each): defaults write com.apple.dock persistent-apps -array-add '{"tile-type"="small-spacer-tile";}' && killall Dock

𝗗𝗶𝘀𝗮𝗯𝗹𝗲 𝗔𝗻𝗻𝗼𝘆𝗶𝗻𝗴 𝗗𝗶𝘀𝗸 𝗪𝗮𝗿𝗻𝗶𝗻𝗴 (must restart Mac to take effect): 
sudo defaults write /Library/Preferences/SystemConfiguration/com.apple.DiskArbitration.diskarbitrationd.plist DADisableEjectNotification -bool YES && sudo pkill diskarbitrationd
𝗥𝗲-𝗘𝗻𝗮𝗯𝗹𝗲 𝗔𝗻𝗻𝗼𝘆𝗶𝗻𝗴 𝗗𝗶𝘀𝗸 𝗪𝗮𝗿𝗻𝗶𝗻𝗴: sudo defaults delete /Library/Preferences/SystemConfiguration/com.apple.DiskArbitration.diskarbitrationd.plist DADisableEjectNotification && sudo pkill diskarbitrationd
𝗔𝗹𝘁𝗲𝗿𝗻𝗮𝘁𝗲𝗹𝘆, 𝗱𝗼𝘄𝗻𝗹𝗼𝗮𝗱 𝗘𝗷𝗲𝗰𝘁𝗶𝗳𝘆: https://ejectify.app

𝗖𝗵𝗮𝗻𝗴𝗲 𝗦𝗰𝗿𝗲𝗲𝗻𝘀𝗵𝗼𝘁 𝗗𝗲𝗳𝗮𝘂𝗹𝘁 𝘁𝗼 𝗝𝗣𝗚 (replace with png to undo): defaults write com.apple.screencapture type jpg

𝗠𝗮𝗸𝗲 𝗛𝗶𝗱𝗱𝗲𝗻 𝗔𝗽𝗽𝘀 𝗧𝗿𝗮𝗻𝘀𝗽𝗮𝗿𝗲𝗻𝘁: cmd + H
defaults write com.apple.Dock showhidden -bool TRUE && killall Dock
```

![[_system/_obsidian/attachments/Untitled.png]]

# BetterTouchTool

[https://folivora.ai/buy](https://folivora.ai/buy)

so you can middle mouse click and like use da vinci when you forget mouse

**Apps to install on Mac (not via appstore)**

underlined = check for settings and custom files etc.

- [x]  Jetbrains toolbox
- [x]  sublime text
- [x]  handbrake
- [x]  spotify
- [ ]  Sejda
- [ ]  R studio, R
- [ ]  Lightroom classic, AE, PS, Media Encoder
- [ ]  Luminar Neo
- [ ]  [vanilla](https://www.youtube.com/redirect?event=video_description&redir_token=QUFFLUhqbUpvWVp1MFRUbXE3Y1dUM2hEZm5wdmhhakpTd3xBQ3Jtc0tsNzBQbFpKbHVONUtXTnRGNHBvaUptWlNvSW5SUEtDTXg3M2VNZUptVXpaS0NCeWRKR2VHMWJjeXQwaHpzdW81YmtEdmRBUjh2NEs4N1pQQzd3Z25WekYwcEQ0WGpoMjExTGxVQXJ4WEV0LWktY0ZjWQ&q=https%3A%2F%2Fmatthewpalmer.net%2Fvanilla%2F&v=e6fLuthfmAs) , bartender?
- [ ]  Raycast search
- [ ]  automator - resize images
- [ ]  AVG antivirus lol
- [ ]  Keyboard Maestro, Espanso
- [ ]  dropzone 4, alttab, https://github.com/MonitorControl/MonitorControl, rectangle
- [ ]  [cheatsheet](https://www.mediaatelier.com/CheatSheet/),
- [ ]  cleanshotx,
- [ ]  system colour picker
- [ ]  neat download manager?
- [ ]  [transmit](https://www.panic.com/transmit/?ref=OliurYouTube) ftp manager
- [ ]  sip - colour picker and palette manager
- [ ]  Alfred
- [ ]  one switch
- [ ]  [eagle](https://eagle.cool/download)
- [ ]  macrium reflect
- [ ]  [filebar](https://apps.apple.com/us/app/id1630856656), [https://hightop.app/](https://hightop.app/), [https://charmstone.app/](https://charmstone.app/)
- [ ]  commander one
- [ ]  syncmate, disk inventory x
- [ ]  iina - videos
- [ ]  the unarchiver
- [ ]  [screen recording](http://www.telestream.net/screenflow/overview.htm#overview) etc -screenflow
- [ ]  [bettertouchtool](https://folivora.ai/buy) - pin tabs, three finger new tab

**Via App Store**

- Roboform
- Da Vinci Resolve

notes

- you can copy text from clipboard on iphone directly to mac - what
- and images - insert - take photo - opens camera app on iphone

IPhone 

Iphone 11 and later - tap and hold shutter button in photo mode to shoot video. Swipe to right to lock. This WORKS WHILE PLAYING MUSIC. 

blackMagic DiskTest

![[_system/_obsidian/attachments/Untitled 1.png]]