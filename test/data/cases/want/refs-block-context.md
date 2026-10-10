A code block in a list item keeps its lines:

-   ```text
    [ref]: https://example.com/a
    ```

A line right after paragraph text stays in the paragraph:
[ref]: https://example.com/b

The first definition of a name wins: [first](https://example.com/first).

A definition in the text wins over the front matter: [fm](https://text.example.com/fm).



Reference:

- dup : [https://example.com/first](https://example.com/first)

- fm : [https://text.example.com/fm](https://text.example.com/fm)


[dup]: https://example.com/first
[fm]: https://text.example.com/fm