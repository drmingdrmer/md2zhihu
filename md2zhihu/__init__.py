import os
import pprint
import re
import shutil
import argparse
import hashlib

import k3down2
import yaml
from k3color import green
from k3color import darkyellow
from k3handy import pjoin
from k3handy import cmd0
from k3handy import to_bytes
from k3handy import cmdpass

from .. import mistune


def sj(*args):
    return ''.join([str(x) for x in args])

def msg(*args):
    print('>', ''.join([str(x) for x in args]))

def indent(line):
    if line == '':
        return ''
    return '    ' + line


def escape(s, quote=True):
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    if quote:
        s = s.replace('"', "&quot;")
    return s


def add_paragraph_end(lines):
    #  add blank line to a paragraph block
    if lines[-1] == '':
        return lines

    lines.append('')
    return lines


def strip_paragraph_end(lines):
    #  remove last blank lines
    if lines[-1] == '':
        return strip_paragraph_end(lines[:-1])

    return lines


def code_join(n):
    lang = n['info'] or ''
    txt = '\n'.join(['```' + lang]
                    + n['text'][:-1].split('\n')
                    + ['```', ''])
    return txt

def code_to_html(n, ctx=None):
    lang = n['info'] or ''
    txt = code_join(n)
    return k3down2.convert('code', txt, 'html').split('\n')

def code_to_jpg(mdrender, n, width=None, ctx=None):
    txt = code_join(n)

    w = width
    if w is None:
        w = mdrender.conf.code_width

    d = k3down2.convert('code', txt, 'jpg', opt={'html': {'width':w}})
    fn = asset_fn(n['text'], 'jpg')
    fwrite(mdrender.conf.output_dir, fn, d)
    return [r'<img src="{}" />'.format(mdrender.conf.img_url(fn)), '']

def code_mermaid_to_jpg(mdrender, n, ctx=None):

    #  strip last \n
    d = k3down2.convert('mermaid', n['text'][:-1], 'jpg')
    fn = asset_fn(n['text'], 'jpg')
    fwrite(mdrender.conf.output_dir, fn, d)

    return [r'![]({})'.format(mdrender.conf.img_url(fn)), '']


def math_block_to_imgtag(n, ctx=None):
    return [k3down2.tex_to_zhihu(n['text'], True)]

def math_inline_to_imgtag(n, ctx=None):
    return [k3down2.tex_to_zhihu(n['text'], False)]

def math_inline_to_plaintext(n, ctx=None):
    return [escape(k3down2.convert('tex_inline', n['text'], 'plain'))]

def table_to_barehtml(mdrender, n, ctx=None):

    # create a markdown render to recursively deal with images etc.
    mdr = MDRender(mdrender.conf, platform=importer)
    md = mdr.render_node(n)
    md = '\n'.join(md)

    tablehtml = k3down2.mdtable_to_barehtml(md)
    return [tablehtml, '']


def table_to_jpg(mdrender, n, ctx=None):

    mdr = MDRender(mdrender.conf, platform='')
    md = mdr.render_node(n)
    md = '\n'.join(md)

    tablehtml = k3down2.md_to_html(md)

    md_base_path = os.path.split(mdrender.conf.md_path)[0]
    d = k3down2.convert('html', tablehtml, 'jpg', opt={'html':{
            'asset_base': os.path.abspath(md_base_path),
    }})

    fn = asset_fn(md, 'jpg')
    fwrite(mdrender.conf.output_dir, fn, d)

    return [r'![]({})'.format(mdrender.conf.img_url(fn)), '']

def importer(mdrender, n, ctx=None):
    '''
    Importer is only used to copy local image to asset dir and update image urls.
    This is used to deal with partial renderers, e.g., table_to_barehtml,
    which is not handled by univertial image importer, but need to import the image when rendering a table with images.
    '''
    typ = n['type']

    if typ == 'image':
        return image_local_to_remote(mdrender, n, ctx=ctx)

    return None

def zhihu_specific(mdrender, n, ctx=None):
    typ = n['type']

    if typ == 'image':
        return image_local_to_remote(mdrender, n, ctx=ctx)

    if typ == 'math_block':
        return math_block_to_imgtag(n, ctx=ctx)

    if typ == 'math_inline':
        return math_inline_to_imgtag(n, ctx=ctx)

    if typ == 'table':
        return table_to_barehtml(mdrender, n, ctx=ctx)

    if typ == 'block_code':
        lang = n['info'] or ''
        if lang == 'mermaid':
            return code_mermaid_to_jpg(mdrender, n, ctx=ctx)

    return None


def wechat_specific(mdrender, n, ctx=None):
    typ = n['type']

    if typ == 'image':
        return image_local_to_remote(mdrender, n, ctx=ctx)

    if typ == 'math_block':
        return math_block_to_imgtag(n, ctx=ctx)

    if typ == 'math_inline':
        return math_inline_to_imgtag(n, ctx=ctx)

    if typ == 'table':
        return table_to_barehtml(mdrender, n, ctx=ctx)

    if typ == 'block_code':
        lang = n['info'] or ''
        if lang == 'mermaid':
            return code_mermaid_to_jpg(mdrender, n, ctx=ctx)

        if lang == '':
            return code_to_jpg(mdrender, n, ctx=ctx)
        else:
            return code_to_jpg(mdrender, n, width=600, ctx=ctx)

    return None

def weibo_specific(mdrender, n, ctx=None):
    typ = n['type']

    if typ == 'image':
        return image_local_to_remote(mdrender, n, ctx=ctx)

    if typ == 'math_block':
        return math_block_to_imgtag(n, ctx=ctx)

    if typ == 'math_inline':
        return math_inline_to_plaintext(n, ctx=ctx)

    if typ == 'table':
        return table_to_jpg(mdrender, n, ctx=ctx)

    if typ == 'codespan':
        return [escape(n['text'])]

    #  weibo does not support pasting <p> in <li>

    if typ == 'list':
        lines = []
        lines.extend(mdrender.render(n['children']))
        lines.append('')
        return lines

    if typ == 'list_item':
        lines = []
        lines.extend(mdrender.render(n['children']))
        lines.append('')
        return lines

    if typ == 'block_quote':
        lines = mdrender.render(n['children'])
        lines = strip_paragraph_end(lines)
        return lines

    if typ == 'block_code':
        lang = n['info'] or ''
        if lang == 'mermaid':
            return code_mermaid_to_jpg(mdrender, n, ctx=ctx)

        if lang == '':
            return code_to_jpg(mdrender, n, ctx=ctx)
        else:
            return code_to_jpg(mdrender, n, width=600, ctx=ctx)

    return None


class MDRender(object):

    # platform specific renderer
    platforms = {
            'zhihu': zhihu_specific,
            'wechat':wechat_specific,
            'weibo':weibo_specific,
    }

    def __init__(self, conf, platform='zhihu'):
        self.conf = conf
        if isinstance(platform, str):
            self.handlers = self.platforms.get(platform, lambda *x, **y:None)
        else:
            self.handlers = platform

    def render_node(self, n, ctx=None):
        """
        Render a AST node into lines of text
        """
        typ = n['type']

        #  customized renderers:

        lines = self.handlers(self, n, ctx=ctx)
        if lines is not None:
            return lines
        else:
            # can not render, continue with default handler
            pass

        # default renderers:

        if typ == 'thematic_break':
            return ['---', '']

        if typ == 'paragraph':
            lines = self.render(n['children'])
            return ''.join(lines).split('\n') + ['']

        if typ == 'text':
            return [n['text']]

        if typ == 'strong':
            lines = self.render(n['children'])
            lines[0] = '**' + lines[0]
            lines[-1] = lines[-1] + '**'
            return lines

        if typ == 'math_block':
            return ['$$', n['text'], '$$']
            #  return [k3down2.tex_to_zhihu(n['text'], True)]

        if typ == 'math_inline':
            return ['$$ ' + n['text'].strip() + ' $$']
            #  return [k3down2.tex_to_zhihu(n['text'], False)]

        if typ == 'table':
            return self.render(n['children']) + ['']

        if typ == 'table_head':
            alignmap = {
                'left': ':--',
                'right': '--:',
                'center': ':-:',
                None: '---',
            }
            lines = self.render(n['children'])
            aligns = [alignmap[x['align']] for x in n['children']]
            aligns = '| ' + ' | '.join(aligns) + ' |'
            return ['| ' + ' | '.join(lines) + ' |', aligns]

        if typ == 'table_cell':
            lines = self.render(n['children'])
            return [''.join(lines)]

        if typ == 'table_body':
            return self.render(n['children'])

        if typ == 'table_row':
            lines = self.render(n['children'])
            return ['| ' + ' | '.join(lines) + ' |']

        if typ == 'block_code':
            # remove the last \n
            return ['```' + (n['info'] or '')] + n['text'][:-1].split('\n') + ['```', '']

        if typ == 'codespan':
            return [('`' + n['text'] + '`')]

        if typ == 'image':
            if n['title'] is None:
                return ['![{alt}]({src})'.format(**n)]
            else:
                return ['![{alt}]({src} {title})'.format(**n)]

        if typ == 'list':
            head = '-   '
            if n['ordered']:
                head = '1.  '

            lines = self.render(n['children'], head)
            return add_paragraph_end(lines)

        if typ == 'list_item':
            lines = self.render(n['children'])
            # ctx is head passed from list
            lines[0] = ctx + lines[0]
            lines = lines[0:1] + [indent(x) for x in lines[1:]]
            return lines

        if typ == 'block_text':
            lines = self.render(n['children'])
            return ''.join(lines).split('\n')

        if typ == 'block_quote':
            lines = self.render(n['children'])
            lines = strip_paragraph_end(lines)
            lines = ['> ' + x for x in lines]
            return lines + ['']

        if typ == 'newline':
            return ['']

        if typ == 'block_html':
            return add_paragraph_end([n['text']])

        if typ == 'link':
            #  TODO title
            lines = self.render(n['children'])
            lines[0] = '[' + lines[0]
            lines[-1] = lines[-1] + '](' + n['link'] + ')'

            return lines

        if typ == 'heading':
            lines = self.render(n['children'])
            lines[0] = '#' * n['level'] + ' ' + lines[0]
            return lines + ['']

        print(typ, n.keys())
        pprint.pprint(n)
        return ['***:' + typ]


    def render(self, nodes, ctx=None):
        rst = []
        for n in nodes:
            rst.extend(self.render_node(n, ctx))

        return rst


def fix_tables(nodes):
    """
    mistune does not parse table in list item.
    We need to recursively fix it.
    """

    for n in nodes:
        if 'children' in n:
            fix_tables(n['children'])

        if n['type'] == 'paragraph':
            children = n['children']

            if len(children) == 0:
                continue

            c0 = children[0]
            if c0['type'] != 'text':
                continue

            txt = c0['text']

            table_reg = r' {0,3}\|(.+)\n *\|( *[-:]+[-| :]*)\n((?: *\|.*(?:\n|$))*)\n*'

            match = re.match(table_reg, txt)
            if match:
                mdr = MDRender(None, platform='')
                partialmd = mdr.render(children)
                partialmd = ''.join(partialmd)

                parser = new_parser()
                new_children = parser(partialmd)
                n['children'] = new_children

def join_math_block(nodes):
    """
    A tex segment may spans several paragraph:

        $$        // paragraph 1
        x = 5     //

        y = 3     // paragraph 2
        $$        //

    This function finds out all such paragraph and merge them into a single one.
    """

    for n in nodes:

        if 'children' in n:
            join_math_block(n['children'])

    join_math_text(nodes)


def parse_math(nodes):
    """
    Extract all math segment such as ``$$ ... $$`` from a text and build a
    math_block or math_inline node.
    """

    children = []

    for n in nodes:

        if 'children' in n:
            n['children'] = parse_math(n['children'])

        if n['type'] == 'text':
            new_children = extract_math(n)
            children.extend(new_children)
        else:
            children.append(n)

    return children


def join_math_text(nodes):
    i = 0
    while i < len(nodes) - 1:
        n1 = nodes[i]
        n2 = nodes[i + 1]
        if ('children' in n1
                and 'children' in n2
                and len(n1['children']) > 0
                and len(n2['children']) > 0
                and n1['children'][-1]['type'] == 'text'
                and n2['children'][0]['type'] == 'text'
                and '$$' in n1['children'][-1]['text']):

            has_dd = '$$' in n2['children'][0]['text']
            n1['children'][-1]['text'] += '\n\n' + n2['children'][0]['text']
            n1['children'].extend(n2['children'][1:])

            nodes.pop(i + 1)

            if has_dd:
                i += 1
        else:
            i += 1


inline_math = r'\$\$(.*?)\$\$'


def extract_math(n):
    """
    Extract ``$$ ... $$`` from a text node and build a new node.
    The original text node is split into multiple segments.
    """
    children = []

    t = n['text']
    while True:
        match = re.search(inline_math, t, flags=re.DOTALL)
        if match:
            children.append({'type': 'text', 'text': t[:match.start()]})
            children.append({'type': 'math_inline', 'text': match.groups()[0]})
            t = t[match.end():]

            left = children[-2]['text']
            right = t
            if (left == '' or left.endswith('\n\n')) and (right == '' or right.startswith('\n')):
                children[-1]['type'] = 'math_block'
            continue

        break
    children.append({'type': 'text', 'text': t})
    return children


def asset_fn(text, suffix):
    textmd5 = hashlib.md5(to_bytes(text)).hexdigest()
    escaped = re.sub(r'[^a-zA-Z0-9_\-=]+', '', text)
    fn = escaped[:32] + '-' + textmd5[:16] + '.' + suffix
    return fn

def image_local_to_remote(mdrender, n, ctx=None):

    #  {'alt': 'openacid',
    #   'src': 'https://...',
    #   'title': None,
    #   'type': 'image'},

    src = n['src']
    if re.match(r'https?://', src):
        return None

    if src.startswith('/'):
        # absolute path from CWD.
        src = src[1:]
    else:
        # relative path from markdown containing dir.
        src = os.path.join(os.path.split(mdrender.conf.md_path)[0], src)

    fn = os.path.split(src)[1]
    shutil.copyfile(src, pjoin(mdrender.conf.output_dir, fn))

    n['src'] = mdrender.conf.img_url(fn)

    # Transform ast node but does not render, leave the task to default image
    # renderer.
    return None


def build_refs(meta):

    dic = {}

    if meta is None:
        return dic

    if 'refs' in meta:
        refs = meta['refs']

        for r in refs:
            dic.update(r)

    platform = 'zhihu'

    if 'platform_refs' in meta:
        refs = meta['platform_refs']
        if platform in refs:
            refs = refs[platform]

            for r in refs:
                dic.update(r)

    return dic


def replace_ref_with_def(nodes, refs):
    for n in nodes:

        if 'children' in n:
            replace_ref_with_def(n['children'], refs)

        if n['type'] == 'text':
            t = n['text']
            link = re.match(r'\[(.*?)\](\[\])?', t)
            if link:
                txt = link.groups()[0]
                if txt in refs:
                    n['type'] = 'link'
                    r = refs[txt]
                    n['link'] = r.split()[0]
                    n['children'] = [{'type': 'text', 'text': txt}]

def new_parser():
    rdr = mistune.create_markdown(
        escape=False,
        renderer='ast',
        plugins=['strikethrough', 'footnotes', 'table'],
    )

    return rdr




def extract_ref_definitions(cont):
    lines = cont.split('\n')
    rst = []
    refs = {}
    for l in lines:
        r = re.match(r'\[(.*?)\]:(.*?)$', l, flags=re.UNICODE)
        if r:
            gs = r.groups()
            refs[gs[0]] = gs[1]
        else:
            rst.append(l)
    return '\n'.join(rst), refs


def extract_jekyll_meta(cont):
    meta = None
    meta_text = None
    m = re.match(r'^ *--- *\n(.*?)\n---\n', cont,
                    flags=re.DOTALL | re.UNICODE)
    if m:
        cont = cont[m.end():]
        meta_text = m.groups()[0].strip()
        meta = yaml.safe_load(meta_text)

    return cont, meta, meta_text


def render_ref_list(refs, platform):

    ref_lines = ["", "Reference:", ""]
    for _id, d in refs.items():
        #  d is in form "<url> <alt>"
        url = d.split()[0]

        ref_lines.append(
                '- {id} : [{url}]({url})'.format(
                        id=_id, url=url
                )
        )

        #  disable paragraph list in weibo
        if platform != 'weibo':
            ref_lines.append('')

    return ref_lines


def fwrite(*p):
    cont = p[-1]
    p = p[:-1]
    with open(os.path.join(*p), 'wb') as f:
        f.write(cont)


class AssetRepo(object):

    def __init__(self, repo_url, cdn=True):

        self.cdn = cdn

        sshurl_fmt = 'git@{host}:{user}/{repo}.git'


        if repo_url is None:
            repo_url = '.'

        # ".": use cwd git
        # ".@foo_branch": use cwd git and specified branch
        if repo_url == '.' or repo_url.startswith('.@'):
            msg("Using current git to store assets...")
            branch = cmd0('git', 'symbolic-ref', '--short', 'HEAD')
            remote = cmd0('git', 'config','--get', 'branch.{}.remote'.format(branch))
            if repo_url.startswith('.@'):
                repo_url = cmd0('git', 'remote', 'get-url', remote) + repo_url[1:]
            else:
                repo_url = cmd0('git', 'remote', 'get-url', remote)

        # git@github.com:openacid/slim.git
        match = re.match(r'git@(.*?):(.*?)/(.*?)\.git(@.*?)?$', repo_url)

        if not match:
            # ssh://git@github.com/openacid/openacid.github.io
            match = re.match(r'ssh://git@(.*?)/(.*?)/(.*?)(@.*?)?$', repo_url)

        if not match:
            # https://github.com/openacid/openacid.github.io.git
            match = re.match(r'https://(.*?)/(.*?)/(.*?)\.git(@.*?)?$', repo_url)



        if not match:
            raise ValueError(
                'unknown url: {sshurl};'
                ' A valid one should be like "{tmpl}" or "{https}"'.format(
                    sshurl=repo_url,
                    tmpl='git@github.com:my_name/my_repo.git'),
                https='https://github.com/my_name/my_repo.git'
            )

        host, user, repo, branch = match.groups()

        url_patterns = {
            'github.com': 'https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}',
            'gitee.com': 'https://gitee.com/{user}/{repo}/raw/{branch}/{path}',
        }

        cdn_patterns = {
            'github.com': 'https://cdn.jsdelivr.net/gh/{user}/{repo}@{branch}/{path}',
        }

        if branch is None:
            cwd = os.getcwd().split(os.path.sep)
            cwdmd5 = hashlib.md5(to_bytes(os.getcwd())).hexdigest()
            branch = '_md2zhihu_{tail}_{md5}'.format(
                    tail=cwd[-1],
                    md5=cwdmd5[:8],
            )
            # escape special chars
            branch = re.sub(r'[^a-zA-Z0-9_\-=]+', '', branch)
        else:
            # @some_branch
            branch = branch[1:]

        self.url = sshurl_fmt.format(host=host,user=user,repo=repo)

        self.host = host
        self.user = user
        self.repo = repo
        self.branch = branch

        ptn = url_patterns[host]
        if self.cdn and host == 'github.com':
            ptn = cdn_patterns[host]

        self.path_pattern = ptn.format(
            user=user,
            repo=repo,
            branch=branch,
            path='{path}')


class Config(object):

    def __init__(self, asset_dir, output_path,
                 platform, md_path, asset_repo_url,
                 code_width=1000):
        self.asset_dir = asset_dir
        self.output_path = output_path
        self.platform = platform
        self.md_path = md_path

        self.asset_repo = AssetRepo(asset_repo_url)
        self.code_width = code_width

        fn = os.path.split(self.md_path)[-1]

        # jekyll style
        fnm = re.match(r'\d\d\d\d-\d\d-\d\d-(.*)', fn)
        if fnm:
            fn = fnm.groups()[0]

        self.article_name = fn.rsplit('.', 1)[0]

        self.rel_dir = pjoin(self.platform, self.article_name)
        self.output_dir = pjoin(self.asset_dir, self.rel_dir)

        if self.output_path is None:
            self.output_path = pjoin(self.output_dir, fn)


    def img_url(self, fn):
        return self.asset_repo.path_pattern.format(
            path=pjoin(self.rel_dir, fn))

    def push(self):
        x = dict(cwd=self.asset_dir)

        cmdpass('git', 'init', **x)
        cmdpass('git', 'add', '.', **x)
        cmdpass('git', 'commit', '--allow-empty', '-m', 'by md2zhihu by drdr.xp@gmail.com', **x)
        cmdpass('git', 'push', '-f', self.asset_repo.url, 'HEAD:refs/heads/' + self.asset_repo.branch, **x)

        msg("Removing tmp git dir: ",self.asset_dir + '/.git')
        shutil.rmtree(self.asset_dir + '/.git')


def main():
    parser = argparse.ArgumentParser(description='Convert markdown to zhihu compatible')

    parser.add_argument('md_path', type=str,
                        help='path to the markdown to process')

    parser.add_argument('-o', '--output', action='store',
                        help='sepcify output path.'
                        ' default: <asset_dir>/<platform>/<fn>/<fn>.md')

    parser.add_argument('-d', '--asset-dir', action='store',
                        default='_md2',
                        help='sepcify directory path to store assets (default: "_md2")')

    parser.add_argument('-r', '--repo', action='store',
                        required=False,
                        default=".",
                        help='sepcify the git url to store assets.'
                             ' The url should be in a SSH form such as:'
                             ' "git@github.com:openacid/openacid.github.io.git[@branch_name]".'
                             ' If no branch is specified, a branch "_md2zhihu_{cwd_tail}_{md5(cwd)[:8]}" is used,'
                             ' in which cwd_tail is the last segment of current working dir.'
                             ' It has to be a public repo and you have the write access.'
                             ' "-r ." to use the git in CWD to store the assets.'
                        )

    parser.add_argument('-p', '--platform', action='store',
                        required=False,
                        default='zhihu',
                        help='convert to a platform compatible format.'
                        ' Supported platform: "zhihu", "wechat"'
    )

    parser.add_argument('--keep-meta', action='store_true',
                        required=False,
                        default=False,
                        help='if keep meta header, which is wrapped with two "---" at file beginning.'
                        ' default: False'
    )

    parser.add_argument('--code-width', action='store',
                        required=False,
                        default=1000,
                        help='specifies code image width.'
                        ' default: 1000'
    )

    args = parser.parse_args()
    msg("Build markdown: ", darkyellow(args.md_path), " into ", darkyellow(args.output))
    msg("Assets will be stored in ", darkyellow(args.repo))

    path = args.md_path

    platform = args.platform
    conf = Config(
        args.asset_dir,
        args.output,
        args.platform,
        path,
        args.repo,
        code_width=args.code_width,
    )

    os.makedirs(conf.output_dir, exist_ok=True)

    with open(path, 'r') as f:
        cont = f.read()

    cont, meta, meta_text = extract_jekyll_meta(cont)
    cont, article_refs = extract_ref_definitions(cont)

    refs = build_refs(meta)
    refs.update(article_refs)

    rdr = new_parser()
    ast = rdr(cont)

    #  with open('ast', 'w') as f:
    #      f.write(pprint.pformat(ast))

    mdr = MDRender(conf, platform=platform)
    fix_tables(ast)

    #  with open('fixed-table', 'w') as f:
    #      f.write(pprint.pformat(ast))

    replace_ref_with_def(ast, refs)

    # extract already inlined math
    ast = parse_math(ast)

    #  with open('after-math-1', 'w') as f:
    #      f.write(pprint.pformat(ast))

    # join cross paragraph math
    join_math_block(ast)
    ast = parse_math(ast)

    #  with open('after-math-2', 'w') as f:
        #  f.write(pprint.pformat(ast))

    out = mdr.render(ast)

    if args.keep_meta:
        out = ['---', meta_text, '---'] + out

    out.append('')

    ref_list = render_ref_list(refs, platform)
    out.extend(ref_list)

    out.append('')

    ref_lines = [
        '[{id}]: {d}'.format(
            id=_id, d=d
        ) for _id, d in refs.items()
    ]
    out.extend(ref_lines)

    with open(conf.output_path, 'w') as f:
        f.write(str('\n'.join(out)))

    msg(sj("Done building ", darkyellow(conf.output_path)))

    msg("Pushing ", darkyellow(conf.asset_dir), " to ", darkyellow(conf.asset_repo.url), " branch: ", darkyellow(conf.asset_repo.branch))
    conf.push()

    msg(green(sj("Great job!!!")), " Built version saved in:")
    msg(darkyellow(conf.output_path))


if __name__ == "__main__":
    main()
