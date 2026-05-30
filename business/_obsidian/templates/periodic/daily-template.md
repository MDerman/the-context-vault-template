---
type: periodic
period: daily
entity: <% tp.file.folder(true).split('/')[0] %>
period_id: <% tp.file.title %>
generated: false
---
# <% tp.file.title %>

<< [[<% tp.date.now("YYYY-MM-DD", -1, tp.file.title, "YYYY-MM-DD") %>]] | [[<% tp.date.now("YYYY-MM-DD", 1, tp.file.title, "YYYY-MM-DD") %>]]>>

[[business#Momentum|Momentum]]

## Tasks

#### New Today
- 

### URGENT + IMPORTANT
*Do it now*

![[business/_obsidian/bases/tasks-eisenhower.base#Urgent Important]]

### URGENT, NOT IMPORTANT
*Delegate or do it after tasks above*

![[business/_obsidian/bases/tasks-eisenhower.base#Urgent Not Important]]

### IMPORTANT, NOT URGENT
*Decide when to do it*

![[business/_obsidian/bases/tasks-eisenhower.base#Important Not Urgent]]

### NOT URGENT, NOT IMPORTANT
*Do it later / Dump it*

![[business/_obsidian/bases/tasks-eisenhower.base#Not Urgent Not Important]]

### Done today

![[business/_obsidian/bases/tasks-eisenhower.base#Done Today]]

## Daily Log

-
