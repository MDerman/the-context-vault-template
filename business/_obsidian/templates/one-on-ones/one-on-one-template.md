<%*
const parts = tp.file.folder(true).split("/");
const folderName = parts[parts.length - 1] || "Unknown";
const rootFolders = new Set(["1-on-1s"]);
const attendee = rootFolders.has(folderName) ? "Unknown" : folderName;
const date = tp.date.now("YYYY-MM-DD");
const compactDate = tp.date.now("YYYYMMDD");
const defaultTitles = new Set(["Untitled", "New note"]);
const targetTitle = `1on1-${attendee}-${compactDate}`;

if (defaultTitles.has(tp.file.title)) {
  await tp.file.rename(targetTitle);
}
-%>
---
title: "<% defaultTitles.has(tp.file.title) ? targetTitle : tp.file.title %>"
type: meeting
meeting_type: 1-on-1
status: draft
date: <% date %>
attendees:
  - <% attendee %>
people:
  - <% attendee %>
project:
source:
tags:
  - work/1on1
---

Date: <% date %>
Attendees: <% attendee %>

<% tp.file.cursor(1) %>

# Agenda
1.

# Notes
-

# New tasks

- 

# Tasks

```tasks
not done
(path includes <% attendee %>) OR (description includes <% attendee %>)
hide edit button
show backlink
short mode
sort by priority, due
```
