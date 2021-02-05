
# 场景和问题

![](https://gitee.com/drdrxp/bed/raw/_md2zhihu_foo/allimg/simple/md----acbd-d573c99c6cf5bbd0.jpg)

![](https://gitee.com/drdrxp/bed/raw/_md2zhihu_foo/allimg/simple/graphLRAHardedge--LinktextBRound-38e149134ebbdae5.jpg)

inline code: `foo = bar`

inline math ![](https://gitee.com/drdrxp/bed/raw/_md2zhihu_foo/allimg/simple/Xvecbeta-Y2-36bbccd5e08c341b.jpg) foo

inline math in codespan `$$ ||X{\vec {\beta }}-Y||^{2} $$`
![](https://gitee.com/drdrxp/bed/raw/_md2zhihu_foo/allimg/simple/slim.jpg)

在时序数据库, 或列存储为基础的系统中, 很常见的形式就是存储一个整数数组,
例如 [slim](https://github.com/openacid/slim) 这个项目按天统计的 star 数:

![](https://gitee.com/drdrxp/bed/raw/_md2zhihu_foo/allimg/simple/slim.jpg)
![](https://gitee.com/drdrxp/bed/raw/_md2zhihu_foo/allimg/simple/slim.jpg)

我们可以利用数据分布的特点, 将整体数据的大小压缩到**几分之一**.

![](https://gitee.com/drdrxp/bed/raw/_md2zhihu_foo/allimg/simple/DatasizeDataSetgzipsizeslimarrys-511b012906c547ff.jpg)

在达到gzip同等压缩率的前提下, 构建 slimarray 和 访问的性能也非常高:

-   构建 slimarray 时, 平均每秒可压缩 6百万 个数组元素;
-   读取一个数组元素平均花费 7 ns/op.
    -   构建 slimarray 时, 平均每秒可压缩 6百万 个数组元素;
    -   读取一个数组元素平均花费 `7 ns/op`.

> 在达到gzip同等压缩率的前提下, 构建 slimarray 和 访问的性能也非常高:
> 
> -   构建 slimarray 时, 平均每秒可压缩 6百万 个数组元素;
> -   读取一个数组元素平均花费 7 ns/op.
>     -   构建 slimarray 时, 平均每秒可压缩 6百万 个数组元素;
>     -   读取一个数组元素平均花费 `7 ns/op`.


按照这种思路, **在给定数组中找到一条曲线来描述点的趋势,**
**再用一个比较小的delta数组修正曲线到实际点的距离, 得到原始值, 就可以实现大幅度的数据压缩. 而且所有的数据都无需解压全部数据就直接读取任意一个.**

# 找到趋势函数

寻找这样一条曲线就使用线性回归,
例如在 [slimarray](https://github.com/openacid/slimarray) 中使用2次曲线 `f(x) = β₁ + β₂x + β₃x²`, 所要做的就是确定每个βᵢ的值,
以使得`f(xⱼ) - yⱼ`的均方差最小. xⱼ是数组下标0, 1, 2...; yⱼ是数组中每个元素的值.

![](https://gitee.com/drdrxp/bed/raw/_md2zhihu_foo/allimg/simple/X=beginbmatrix1x_1x_121x_2x_22vd-804a1197af934f48.jpg)

`spanIndex = OnesCount(bitmap & (1<<(i/16) - 1))`

## 读取过程

读取过程通过找span, 读取span配置,还原原始数据几个步骤完成, 假设 slimarray 的对象是`sa`:

-   通过下标`i` 得到 spanIndex: `spanIndex = OnesCount(sa.bitmap & (1<<(i/16) - 1))`;
-   通过 spanIndex 得到多项式的3个系数: `[b₀, b₁, b₂] = sa.polynomials[spanIndex: spanIndex + 3]`;
-   读取 delta 数组起始位置, 和 delta 数组中每个 delta 的 bit 宽度: `config=sa.configs[spanIndex]`;
-   delta 的值保存在 delta 数组的`config.offset + i*config.width`的位置, 从这个位置读取`width`个 bit 得到 delta 的值.
-   计算 `nums[i]` 的值: `b₀ + b₁*i + b₂*i²` 再加上 delta 的值.

简化的读取逻辑如下:

<img src="https://gitee.com/drdrxp/bed/raw/_md2zhihu_foo/allimg/simple/funcsmSlimArrayGetiint32uint32x=-8e29c97c1ebbd46d.jpg" />

formula in list:

-   对奇数节点, n = 2k+1, 还是沿用 **多数派** 节点的集合, 大部分场合都可以很好的工作:

    ![](https://gitee.com/drdrxp/bed/raw/_md2zhihu_foo/allimg/simple/Q_oddC=MC=qqsubseteqCqC2-149709b0ed354902.jpg)

-   对偶数节点, n = 2k, **因为n/2个节点跟n/2+1个节点一定有交集**,
    我们可以向 M(C) 中加入几个大小为 n/2 的节点集合,

    以本文的场景为例,

    -   可以设置 Q' = M(abcd) ∪ {ab, bc, ca}, Q'中任意2个元素都有交集;
    -   也可以是 Q' = M(abcd) ∪ {bc, cd, bd};

    要找到一个更好的偶节点的 quorum 集合, 一个方法是可以把偶数节点的集群看做是一个奇数节点集群加上一个节点x:
    ![](https://gitee.com/drdrxp/bed/raw/_md2zhihu_foo/allimg/simple/D=Ccupx-76874c18ea7bc229.jpg)

    于是偶数节点的 quorum 集合就可以是 M(D) 的一个扩张:

    ![](https://gitee.com/drdrxp/bed/raw/_md2zhihu_foo/allimg/simple/Q_evenD_x=MDcupMDsetminusx-d979aeb5e8ea9324.jpg)

    当然这个x可以随意选择, 例如在abcd的例子中, 如果选x = d, 那么
    Q' = M(abcd) ∪ {ab, bc, ca};

table in list:

-   链接列表:

    ![](https://gitee.com/drdrxp/bed/raw/_md2zhihu_foo/allimg/simple/---assetsslimjpgfobarabc-4eb2fd74bec19f90.jpg)



Reference:

- slim : [https://github.com/openacid/slim](https://github.com/openacid/slim)

- slimarray : [https://github.com/openacid/slimarray](https://github.com/openacid/slimarray)

- vlink : [https://vlink.zhihu](https://vlink.zhihu)

- text-ref : [https://foo.com](https://foo.com)


[slim]: https://github.com/openacid/slim "slim"
[slimarray]: https://github.com/openacid/slimarray "slimarray"
[vlink]: https://vlink.zhihu "vlink"
[text-ref]:  https://foo.com
