<%*
const date = tp.date.now("YYYY-MM-DD");
const defaultTitles = new Set(["Untitled", "New note"]);
const targetTitle = `founder-note-${date}`;
if (defaultTitles.has(tp.file.title)) {
  await tp.file.rename(targetTitle);
}
-%>
---
title: "<% defaultTitles.has(tp.file.title) ? targetTitle : tp.file.title %>"
type: meeting
meeting_type: founder-note
status: draft
date: <% date %>
project:
people:
source:
---

# <% defaultTitles.has(tp.file.title) ? targetTitle : tp.file.title %>

## Decisions needed

- 

## Product

- 

## GTM

- 

## Customers / leads

- 

## Blockers

- 

## Follow-ups

- [ ] 
