<%*
const date = tp.date.now("YYYY-MM-DD");
const defaultTitles = new Set(["Untitled", "New note"]);
const targetTitle = `customer-call-${date}`;
if (defaultTitles.has(tp.file.title)) {
  await tp.file.rename(targetTitle);
}
-%>
---
title: "<% defaultTitles.has(tp.file.title) ? targetTitle : tp.file.title %>"
type: meeting
meeting_type: customer-call
status: draft
date: <% date %>
project:
people:
company:
source:
---

# <% defaultTitles.has(tp.file.title) ? targetTitle : tp.file.title %>

## Context

- Person:
- Company:
- Source:

## What they said

- 

## Pain / jobs

- 

## Objections

- 

## Feature requests

- 

## Testimonials / proof

- 

## Follow-ups

- [ ] 

## Signals to create

- 
