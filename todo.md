
- local convert:
    md2zhihu input.md \
    --output-dir oo/
    --feature image:local_to_remote
    --feature math_block:to_jpg
    --feature block_code/mermaid:to_jpg
    --feature block_code/:to_jpg
    --feature block_code/*:to_jpg


- optional push to a repo


md2zhihu --repo .                   # default remote, default branch
md2zhihu --repo .@brach             # default remote
md2zhihu --repo remote@brach

