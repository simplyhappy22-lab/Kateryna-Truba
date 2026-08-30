# Походження скілів

Усі скіли в цій теці — сторонні, скопійовані з публічних репозиторіїв під ліцензією MIT.
Тексти ліцензій лежать у `licenses/`.

| Скіл | Джерело | Автор | Ліцензія | Комміт |
|---|---|---|---|---|
| `i-have-adhd` | [ayghri/i-have-adhd](https://github.com/ayghri/i-have-adhd) | Aymane Ghribi | MIT | `cbe69fb` |
| `avoid-ai-writing` | [conorbronsdon/avoid-ai-writing](https://github.com/conorbronsdon/avoid-ai-writing) | Conor Bronsdon | MIT | `58a95fc` |
| `ukrainianizer` | [vitalii4reva/ukrainianizer](https://github.com/vitalii4reva/ukrainianizer) | vitalii4reva | MIT | `0bf3047` |
| `blog-draft` | [luongnv89/claude-howto](https://github.com/luongnv89/claude-howto) (`uk/03-skills/blog-draft`) | luongnv89 | MIT | `28149a8` |
| `blog-outline` | [AgriciDaniel/claude-blog](https://github.com/AgriciDaniel/claude-blog) (`skills/blog-outline`) | Agrici Daniel | MIT | `84f7abf` |
| `blog-repurpose` | [AgriciDaniel/claude-blog](https://github.com/AgriciDaniel/claude-blog) (`skills/blog-repurpose`) | Agrici Daniel | MIT | `84f7abf` |
| `article-extractor` | [michalparkola/tapestry-skills](https://github.com/michalparkola/tapestry-skills) | Michal Parkola | MIT | `80e1dc5` |
| `youtube-transcript` | [michalparkola/tapestry-skills](https://github.com/michalparkola/tapestry-skills) | Michal Parkola | MIT | `80e1dc5` |

## Внесені правки

Файли скопійовані майже дослівно. Чотири відхилення, потрібні щоб скіли працювали окремо
від своїх материнських репозиторіїв і не конфліктували між собою:

1. `blog-repurpose/SKILL.md` — шлях до довідника змінено з `skills/blog/references/flow-alignment.md`
   на `references/flow-alignment.md`, бо тут немає скіла-оркестратора `blog`. Сам довідник
   скопійовано з того ж репозиторію.
2. `blog-draft/SKILL.md` — блок-заповнювач `$ARGUMENTS` (синтаксис слеш-команд Claude Code,
   який Cursor не підставляє) замінено на вказівку брати тему з діалогу.
3. `blog-outline`, `blog-repurpose` — узято лише окремі підскіли з набору `claude-blog` на 32 скіли.
   Ті підскіли, що залежать від довідників оркестратора (`blog-strategy`, `blog-calendar`),
   не копіювалися — для них ставте повний набір, див. README.
4. `avoid-ai-writing/SKILL.md` — в `description` додано, що скіл лише для англійського тексту,
   і посилання на `ukrainianizer` для українського. Без цього два скіли конкурують за одне
   й те саме завдання: Cursor вибирає скіл на основі `description`, а документованого
   правила пріоритету для скілів, що перетинаються, не існує.

## Як оновити скіл

```bash
# приклад: оновити avoid-ai-writing
git clone --depth 1 https://github.com/conorbronsdon/avoid-ai-writing /tmp/aaw
cp /tmp/aaw/SKILL.md .cursor/skills/avoid-ai-writing/SKILL.md
cp -r /tmp/aaw/scripts /tmp/aaw/examples .cursor/skills/avoid-ai-writing/
```

Після оновлення перевірте, що поле `name` у frontmatter усе ще збігається з назвою теки —
Cursor цього вимагає.
