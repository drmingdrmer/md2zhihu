
# 场景和问题

![](https://gitee.com/drdrxp/bed/raw/_md2zhihu/zhihu/simple/graphLRAHardedge--LinktextBRound-38e149134ebbdae5.jpg)

在时序数据库, 或列存储为基础的系统中, 很常见的形式就是存储一个整数数组,
例如 [slim](https://github.com/openacid/slim) 这个项目按天统计的 star 数:

![](https://gitee.com/drdrxp/bed/raw/_md2zhihu/zhihu/simple/slim.jpg)
![](https://gitee.com/drdrxp/bed/raw/_md2zhihu/zhihu/simple/slim.jpg)

我们可以利用数据分布的特点, 将整体数据的大小压缩到**几分之一**.

<table>
<tr class="header">
<th style="text-align: right;">Data size</th>
<th style="text-align: left;">Data Set</th>
<th style="text-align: right;">gzip size</th>
<th style="text-align: left;">slimarry size</th>
<th style="text-align: right;">avg size</th>
<th style="text-align: right;">ratio</th>
</tr>
<tr class="odd">
<td style="text-align: right;">1,000</td>
<td style="text-align: left;">rand u32: [0, 1000]</td>
<td style="text-align: right;">x</td>
<td style="text-align: left;">824 byte</td>
<td style="text-align: right;">6 bit/elt</td>
<td style="text-align: right;">18%</td>
</tr>
<tr class="even">
<td style="text-align: right;">1,000,000</td>
<td style="text-align: left;">rand u32: [0, 1000,000]</td>
<td style="text-align: right;">x</td>
<td style="text-align: left;">702 KB</td>
<td style="text-align: right;">5 bit/elt</td>
<td style="text-align: right;">15%</td>
</tr>
<tr class="odd">
<td style="text-align: right;">1,000,000</td>
<td style="text-align: left;">IPv4 DB</td>
<td style="text-align: right;">2 MB</td>
<td style="text-align: left;">2 MB</td>
<td style="text-align: right;">16 bit/elt</td>
<td style="text-align: right;">50%</td>
</tr>
<tr class="even">
<td style="text-align: right;">600</td>
<td style="text-align: left;"><a href="https://github.com/openacid/slim">slim</a> star count</td>
<td style="text-align: right;">602 byte</td>
<td style="text-align: left;">832 byte</td>
<td style="text-align: right;">10 bit/elt</td>
<td style="text-align: right;">26%</td>
</tr>
</table>

在达到gzip同等压缩率的前提下, 构建 slimarray 和 访问的性能也非常高:

-   构建 slimarray 时, 平均每秒可压缩 6百万 个数组元素;
-   读取一个数组元素平均花费 7 ns/op.
    -   构建 slimarray 时, 平均每秒可压缩 6百万 个数组元素;
    -   读取一个数组元素平均花费 `7 ns/op`.

🤔!!!

按照这种思路, **在给定数组中找到一条曲线来描述点的趋势,**
**再用一个比较小的delta数组修正曲线到实际点的距离, 得到原始值, 就可以实现大幅度的数据压缩. 而且所有的数据都无需解压全部数据就直接读取任意一个.**

# 找到趋势函数

寻找这样一条曲线就使用线性回归,
例如在 [slimarray](https://github.com/openacid/slimarray) 中使用2次曲线 `f(x) = β₁ + β₂x + β₃x²`, 所要做的就是确定每个βᵢ的值,
以使得`f(xⱼ) - yⱼ`的均方差最小. xⱼ是数组下标0, 1, 2...; yⱼ是数组中每个元素的值.

<img src="https://www.zhihu.com/equation?tex=X%20%3D%20%5Cbegin%7Bbmatrix%7D1%20%20%20%20%20%20%26%20x_1%20%20%20%20%26%20x_1%5E2%20%5C%5C1%20%20%20%20%20%20%26%20x_2%20%20%20%20%26%20x_2%5E2%20%5C%5C%5Cvdots%20%26%20%5Cvdots%20%26%20%5Cvdots%20%20%20%20%5C%5C1%20%20%20%20%20%20%26%20x_n%20%20%20%20%26%20x_n%5E2%5Cend%7Bbmatrix%7D%2C%5Cvec%7B%5Cbeta%7D%20%3D%5Cbegin%7Bbmatrix%7D%5Cbeta_1%20%5C%5C%5Cbeta_2%20%5C%5C%5Cbeta_3%20%5C%5C%5Cend%7Bbmatrix%7D%2CY%20%3D%5Cbegin%7Bbmatrix%7Dy_1%20%5C%5Cy_2%20%5C%5C%5Cvdots%20%5C%5Cy_n%5Cend%7Bbmatrix%7D%5C%5C" alt="X = \begin{bmatrix}1      & x_1    & x_1^2 \\1      & x_2    & x_2^2 \\\vdots & \vdots & \vdots    \\1      & x_n    & x_n^2\end{bmatrix},\vec{\beta} =\begin{bmatrix}\beta_1 \\\beta_2 \\\beta_3 \\\end{bmatrix},Y =\begin{bmatrix}y_1 \\y_2 \\\vdots \\y_n\end{bmatrix}\\" class="ee_img tr_noresize" eeimg="1">

`spanIndex = OnesCount(bitmap & (1<<(i/16) - 1))`

## 读取过程

读取过程通过找span, 读取span配置,还原原始数据几个步骤完成, 假设 slimarray 的对象是`sa`:

-   通过下标`i` 得到 spanIndex: `spanIndex = OnesCount(sa.bitmap & (1<<(i/16) - 1))`;
-   通过 spanIndex 得到多项式的3个系数: `[b₀, b₁, b₂] = sa.polynomials[spanIndex: spanIndex + 3]`;
-   读取 delta 数组起始位置, 和 delta 数组中每个 delta 的 bit 宽度: `config=sa.configs[spanIndex]`;
-   delta 的值保存在 delta 数组的`config.offset + i*config.width`的位置, 从这个位置读取`width`个 bit 得到 delta 的值.
-   计算 `nums[i]` 的值: `b₀ + b₁*i + b₂*i²` 再加上 delta 的值.

简化的读取逻辑如下:

```go
func (sm *SlimArray) Get(i int32) uint32 {

    x := float64(i)

    bm := sm.spansBitmap & bitmap.Mask[i>>4]
    spanIdx := bits.OnesCount64(bm)

    j := spanIdx * polyCoefCnt
    p := sm.Polynomials
    v := int64(p[j] + p[j+1]*x + p[j+2]*x*x)

    config := sm.Configs[spanIdx]
    deltaWidth := config & 0xff
    offset := config >> 8

    bitIdx := offset + int64(i)*deltaWidth

    d := sm.Deltas[bitIdx>>6]
    d = d >> uint(bitIdx&63)

    return uint32(v + int64(d&bitmap.Mask[deltaWidth]))
}
```


[slim]: https://github.com/openacid/slim "slim"
[slimarray]: https://github.com/openacid/slimarray "slimarray"
