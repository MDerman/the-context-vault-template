---
type: periodic
period: daily
entity: <% tp.file.folder(true).split('/')[0] %>
period_id: <% tp.file.title %>
generated: false
---
## Links
- [[<% tp.file.folder(true).split('/')[0] %>/_obsidian/periodic/weekly/<% tp.date.now("GGGG-[W]WW", 0, tp.file.title, "YYYY-MM-DD") %>|Weekly note]]
- [[<% tp.file.folder(true).split('/')[0] %>/_obsidian/periodic/quarterly/<% tp.date.now("YYYY-[Q]Q", 0, tp.file.title, "YYYY-MM-DD") %>|Quarterly note]]
- [[Dashboard]]
- [[_master/_obsidian/bases/tasks-kanban.base|tasks-kanban]]
- [[Daily What To Do]]
- [[personal#Momentum|Personal Momentum]]
- [[Keep in minds]]

# Super-alignment
## 📒 ~5 Tasks I want to get done today
- 
---
## Manifestation statement:

---
## Highlight
*(criteria: Importance, Urgency, Satisfaction, Joy)*

---
## What are the specific results I want to produce today?

---
## What am I grateful for today?

---
## Daily Number 1s:
- **Health*:* 
- **Work**: 
- **Relationship**: 

> Actively seek opportunities to do the things I love and will fulfil me today. 
> Work expands to fill the time you assign to it.

---

# Daily Review
## 📒 Contract for what I'm doing tomorrow (sign it)

---
- [ ] Review calendar for tomorrow, calendar block, and review what I actually spent time on today (no hard feelings)
- [ ] How did my highlight go / What could I have done better today?
- [ ] Any big wins?

---
# Journal Entry

<% tp.file.cursor() %>

---
On this day last year <% tp.date.now("YYYY-MM-DD", "P-1Y") %>
---


## Reference
- 📒 -> 2 essential things that must at least be done each day, and are usually completed in physical notebook.
