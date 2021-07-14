
-   Assets used by a markdown are pushed to a branch and the urls in the markdown are replaced.

    Assets are stored in a branch specified by `inputs.asset_branch`, by default
    `_md2zhihu/asset`.

    It pushes converted markdowns to a branch specified by `inputs.md_branch`,
    by default `_md2zhihu/md`.
    To retrieve the converted markdowns, a user fetches and merges this branch.

-   Latex math such as `$$ \frac{x}{y} $$` are converted into images.

