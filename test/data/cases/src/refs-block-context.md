---
refs:
    - "fm": https://front-matter.example.com/fm "From front matter"
---

A code block in a list item keeps its lines:

- ```text
  [ref]: https://example.com/a
  ```

A line right after paragraph text stays in the paragraph:
[ref]: https://example.com/b

The first definition of a name wins: [first][dup].

[dup]: https://example.com/first
[dup]: https://example.com/second

A definition in the text wins over the front matter: [fm][].

[fm]: https://text.example.com/fm
