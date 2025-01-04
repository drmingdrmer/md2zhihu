
# Transparent Test

Table should pass through:

|  | col1 | col2 |
| :-- | :-: | :-: |
| row1 | a | b |
| row2 | c | d |

```mermaid
graph LR
    A --> B
```

```graphviz
digraph G {
    a -> b
}
```

Inline math $$ x = y $$ should pass through.

Block math:

$$
\sum_{i=1}^{n} i = \frac{n(n+1)}{2}
$$

Code block:

```go
func main() {
    fmt.Println("hello")
}
```

Image should be processed:
![](transparent/18b61671112f3aeb-slim.jpg)

Reference link [slim](https://github.com/openacid/slim) should pass through unchanged.



Reference:

- slim : [https://github.com/openacid/slim](https://github.com/openacid/slim)


[slim]: https://github.com/openacid/slim "slim"