# Transparent Test

Table should pass through:

<table>
<tr class="header">
<th style="text-align: left;"></th>
<th style="text-align: center;">col1</th>
<th style="text-align: center;">col2</th>
</tr>
<tr class="odd">
<td style="text-align: left;">row1</td>
<td style="text-align: center;">a</td>
<td style="text-align: center;">b</td>
</tr>
<tr class="even">
<td style="text-align: left;">row2</td>
<td style="text-align: center;">c</td>
<td style="text-align: center;">d</td>
</tr>
</table>

![](https://cdn.jsdelivr.net/gh/drmingdrmer/md2test@action_test/transparent/graphLRA--B-5aa891fa11324350.jpg)

![](https://cdn.jsdelivr.net/gh/drmingdrmer/md2test@action_test/transparent/digraphGa-b-1d1e266ebb4e46bd.jpg)

Inline math <img src="https://www.zhihu.com/equation?tex=%20x%20%3D%20y%20" alt=" x = y " class="ee_img tr_noresize" eeimg="1"> should pass through.

Block math:

<img src="https://www.zhihu.com/equation?tex=%20%5Csum_%7Bi%3D1%7D%5E%7Bn%7D%20i%20%3D%20%5Cfrac%7Bn%28n%2B1%29%7D%7B2%7D%20%5C%5C" alt=" \sum_{i=1}^{n} i = \frac{n(n+1)}{2} \\" class="ee_img tr_noresize" eeimg="1">

Code block:

```go
func main() {
    fmt.Println("hello")
}
```

Image should be processed:
![](https://cdn.jsdelivr.net/gh/drmingdrmer/md2test@action_test/transparent/18b61671112f3aeb-slim.jpg)

Reference link [slim](https://github.com/openacid/slim "slim") should pass through unchanged.



Reference:

- slim : [https://github.com/openacid/slim](https://github.com/openacid/slim)


[slim]: https://github.com/openacid/slim "slim"