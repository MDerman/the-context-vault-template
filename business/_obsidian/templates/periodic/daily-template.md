---
type: periodic
period: daily
entity: <% tp.file.folder(true).split('/')[0] %>
period_id: <% tp.file.title %>
generated: false
---
# <% tp.file.title %>

<< [[<% tp.date.now("YYYY-MM-DD", -1, tp.file.title, "YYYY-MM-DD") %>]] | [[<% tp.date.now("YYYY-MM-DD", 1, tp.file.title, "YYYY-MM-DD") %>]]>>

## Daily Goals (5 max)

- [ ]
- [ ]
- [ ]
- [ ]
- [ ]

## Daily Review & Wins

-
