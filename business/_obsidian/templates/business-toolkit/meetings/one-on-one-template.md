<%*
const date = tp.date.now("YYYY-MM-DD");
const defaultTitles = new Set(["Untitled", "New note"]);
const targetTitle = `one-on-one-${date}`;
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
people:
project:
source:
---

# <% defaultTitles.has(tp.file.title) ? targetTitle : tp.file.title %>

## Agenda

1. 

## Notes

- 

## Decisions

- 

## Follow-ups

- [ ] 
