A tight list stays tight:

- text before code:
  ```
  code
  ```
- ```
  code
  ```
  text after the code
- > quote
  >
  text after the quote
- # heading
  text after the heading
- nested list:
  - nested item
- last item

A block that converts to an image keeps the blank line after it, so the list becomes loose:

- ```mermaid
  graph LR
  ```
  text after the mermaid
- last item
