---
spiritual:
wife:
kids:
friend:
learn:
create:
exercise:
reading: false
writing: false
planning: false
shutdown: false
prayer: false
---
wads
on this day [[<% tp.date.now("YYYY-MM-DD","P-1Y*) 
%>]]



> [!memento-mori]+ Memento Mori
> ```dataviewjs
> const today = dv.date('{{date:YYYY-MM-DD}}')
> const endOfYear = {
> year: today.year,
> }
> 
> const lifespan = { year: 80 }
> const birthday = DateTime.fromObject({
> year: 1990,
> month: 12,
> day: 31
> });
> 
> const deathday = birthday.plus(lifespan)
> function progress(type) {
> let value;
> switch(type) {
> case "lifespan":
> value = (today.year - birthday.year) / lifespan.year * 100;
> break;
> }
> 
> return `<progress value="${parseInt(value)}" max="100"></progress> &nbsp;&nbsp; ${parseInt(value)} %`
> 
> }
> 
> dv.span(`
> ${progress("lifespan")}
> `)
> 
> ```


> [!affirmations]- Affirmations
> - I am a successful business-owner and I know what I'm doing.
> - I am able and willing to help people make sense of big ideas.
> - I am a competent coach who can help people get to the next level of their creator business.


> [!reading]+ Bible Reading
> ```tasks
> due {{date:YYYY-MM-DD}}
> tags includes #biblereading
> hide tags
> short mode
> ```

> [!todo]+ Tasks
> ```tasks
> not done
> (due on or before {{date:YYYY-MM-DD}}) OR (scheduled on or before {{date:YYYY-MM-DD}})
> filename does not include Chronological Bible Reading Plan
> short mode
> ```

> [!habits]+ Habits
> - [ ] Writing
> - [ ] Reading
> - [ ] Planning


```ktr-heatmap
WEEKS 52
```

### Wins

### Journal Entries

### Gratitude

### Stories

### Links

### Review

```base
filters:
  or:
    - file.inFolder("Daily Notes")
formulas:
  on_this_day: if(date(file.name).month == "{{DATE:MM}}", if(date(file.name).day == "{{DATE:DD}}", if(date(file.name).year != "{{DATE:YYYY}}", "True", "False"), "False"), "False")
properties:
  file.name:
    displayName: Daily Note
views:
  - type: table
    name: On This Day
    filters:
      and:
        - formula.on_this_day.contains("True")
    order:
      - file.name
    sort:
      - property: file.name
        direction: DESC
    formula.on_this_day:
      displayName: On This Day
```

