import argparse
import hashlib
import os
import pprint
import re
import shutil

import k3down2
import k3git
import yaml
from k3color import darkyellow
from k3color import green
from k3handy import cmdpass
from k3handy import pjoin
from k3handy import to_bytes
from k3fs import fread

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


def block_code_to_jpg(mdrender, n, width=None, ctx=None):
    txt = code_join(n)

    w = width
    if w is None:
        w = mdrender.conf.code_width

    return typ_text_to_jpg(mdrender, 'code', txt, opt={'html': {'width': w}})


def block_code_to_fixwidth_jpg(mdrender, n, ctx=None):
    return block_code_to_jpg(mdrender, n, width=600, ctx=ctx)


def block_code_mermaid_to_jpg(mdrender, n, ctx=None):
    return typ_text_to_jpg(mdrender, 'mermaid', n['text'])


def block_code_graphviz_to_jpg(mdrender, n, ctx=None):
    return typ_text_to_jpg(mdrender, 'graphviz', n['text'])


def typ_text_to_jpg(mdrender, typ, txt, opt=None):
    d = k3down2.convert(typ, txt, 'jpg', opt=opt)
    fn = asset_fn(txt, 'jpg')
    fwrite(mdrender.conf.asset_output_dir, fn, d)

    return [r'![]({})'.format(mdrender.conf.img_url(fn)), '']


def math_block_to_imgtag(mdrender, n, ctx=None):
    return [k3down2.convert('tex_block', n['text'], 'imgtag')]


def math_inline_to_imgtag(mdrender, n, ctx=None):
    return [k3down2.convert('tex_inline', n['text'], 'imgtag')]


def math_block_to_jpg(mdrender, n, ctx=None):
    return typ_text_to_jpg(mdrender, 'tex_block', n['text'])


def math_inline_to_jpg(mdrender, n, ctx=None):
    return typ_text_to_jpg(mdrender, 'tex_inline', n['text'])


def math_inline_to_plaintext(mdrender, n, ctx=None):
    return [escape(k3down2.convert('tex_inline', n['text'], 'plain'))]


def to_plaintext(mdrender, n, ctx=None):
    return [escape(n['text'])]


def table_to_barehtml(mdrender, n, ctx=None):

    # create a markdown render to recursively deal with images etc.
    mdr = MDRender(mdrender.conf, platform=importer)
    md = mdr.render_node(n)
    md = '\n'.join(md)

    tablehtml = k3down2.convert('table', md, 'html')
    return [tablehtml, '']


def table_to_jpg(mdrender, n, ctx=None):

    mdr = MDRender(mdrender.conf, platform='')
    md = mdr.render_node(n)
    md = '\n'.join(md)

    md_base_path = os.path.split(mdrender.conf.src_path)[0]

    return typ_text_to_jpg(mdrender, 'md', md, opt={'html': {
        'asset_base': os.path.abspath(md_base_path),
    }})


def importer(mdrender, n, ctx=None):
    '''
    Importer is only used to copy local image to output dir and update image urls.
    This is used to deal with partial renderers, e.g., table_to_barehtml,
    which is not handled by univertial image importer, but need to import the image when rendering a table with images.
    '''
    typ = n['type']

    if typ == 'image':
        return image_local_to_remote(mdrender, n, ctx=ctx)

    return None


def zhihu_specific(mdrender, n, ctx=None):
    return render_with_features(mdrender, n, ctx=ctx, features=zhihu_features)


def minimal_mistake_specific(mdrender, n, ctx=None):
    return render_with_features(mdrender, n, ctx=ctx, features=minimal_mistake_features)


def wechat_specific(mdrender, n, ctx=None):
    return render_with_features(mdrender, n, ctx=ctx, features=wechat_features)


def weibo_specific(mdrender, n, ctx=None):
    typ = n['type']

    if typ == 'image':
        return image_local_to_remote(mdrender, n, ctx=ctx)

    if typ == 'math_block':
        return math_block_to_imgtag(mdrender, n, ctx=ctx)

    if typ == 'math_inline':
        return math_inline_to_plaintext(mdrender, n, ctx=ctx)

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
            return block_code_mermaid_to_jpg(mdrender, n, ctx=ctx)
        if lang == 'graphviz':
            return block_code_graphviz_to_jpg(mdrender, n, ctx=ctx)

        if lang == '':
            return block_code_to_jpg(mdrender, n, ctx=ctx)
        else:
            return block_code_to_jpg(mdrender, n, width=600, ctx=ctx)

    return None


def simple_specific(mdrender, n, ctx=None):
    return render_with_features(mdrender, n, ctx=ctx, features=simple_features)


class MDRender(object):

    # platform specific renderer
    platforms = {
        'zhihu': zhihu_specific,
        'wechat': wechat_specific,
        'weibo': weibo_specific,
        'minimal_mistake': minimal_mistake_specific,
        'simple': simple_specific,
    }

    def __init__(self, conf, platform='zhihu'):
        self.conf = conf
        if isinstance(platform, str):
            self.handlers = self.platforms.get(platform, lambda *x, **y: None)
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

        if typ == 'math_inline':
            return ['$$ ' + n['text'].strip() + ' $$']

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

        if typ == 'strikethrough':
            lines = self.render(n['children'])
            lines[0] = '~~' + lines[0]
            lines[-1] = lines[-1] + '~~'
            return lines

        if typ == 'emphasis':
            lines = self.render(n['children'])
            lines[0] = '*' + lines[0]
            lines[-1] = lines[-1] + '*'
            return lines

        if typ == 'inline_html':
            return [n['text']]

        if typ == 'linebreak':
            return ["  \n"]

        print(typ, n.keys())
        pprint.pprint(n)
        return ['***:' + typ]

    def render(self, nodes, ctx=None):
        rst = []
        for n in nodes:
            rst.extend(self.render_node(n, ctx))

        return rst

    def msg(self, *args):
        msg(*args)


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
        src = os.path.join(os.path.split(mdrender.conf.src_path)[0], src)

    fn = os.path.split(src)[1]
    shutil.copyfile(src, pjoin(mdrender.conf.asset_output_dir, fn))

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
    """
    Convert ``[text][link-def]`` to ``[text](link-url)``
    Convert ``[link-def][]``     to ``[link-def](link-url)``
    Convert ``[link-def]``       to ``[link-def](link-url)``
    """

    used_defs={}

    for n in nodes:

        if 'children' in n:
            used = replace_ref_with_def(n['children'], refs)
            used_defs.update(used)

        if n['type'] == 'text':
            t = n['text']
            link = re.match(r'^\[(.*?)\](\[([0-9a-zA-Z_\-]*?)\])?$', t)
            if not link:
                continue

            gs = link.groups()
            txt = gs[0]
            if len(gs) >= 3:
                definition = gs[2]

            if definition is None or definition == '':
                definition = txt

            if definition in refs:
                n['type'] = 'link'
                r = refs[definition]
                #  TODO title
                n['link'] = r.split()[0]
                n['children'] = [{'type': 'text', 'text': txt}]
                used_defs[definition] = r

    return used_defs


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
        url_alt = d.split()
        url = url_alt[0]

        if len(url_alt) == 1:
            txt = _id
        else:
            txt = ' '.join(url_alt[1:])
            txt = txt.strip('"')
            txt = txt.strip("'")

        ref_lines.append(
            '- {id} : [{url}]({url})'.format(
                id=txt, url=url
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


class LocalRepo(object):
    is_local = True
    """
    Create relative path for url in ``md_path` pointing to ``asset_dir_path``.
    """

    def __init__(self, md_path, asset_dir_path):
        md_base = os.path.split(md_path)[0]
        rel = os.path.relpath(asset_dir_path, start=md_base, )
        if rel == '.':
            rel = ''
        self.path_pattern = pjoin(rel, '{path}')


class AssetRepo(object):

    is_local = False

    def __init__(self, repo_url, cdn=True):
        #  TODO: test rendering md rendering with pushed assets

        self.cdn = cdn

        repo_url = self.parse_shortcut_repo_url(repo_url)

        gu = k3git.GitUrl.parse(repo_url)
        f = gu.fields

        if (f['scheme'] == 'https'
                and 'committer' in f
                and 'token' in f):
            url = gu.fmt(scheme='https')
        else:
            url = gu.fmt(scheme='ssh')

        host, user, repo, branch = (
            f.get('host'),
            f.get('user'),
            f.get('repo'),
            f.get('branch'),
        )
        print("branch:", branch)
        print(f)

        self.url = url

        url_patterns = {
            'github.com': 'https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}',
            'gitee.com': 'https://gitee.com/{user}/{repo}/raw/{branch}/{path}',
        }

        cdn_patterns = {
            'github.com': 'https://cdn.jsdelivr.net/gh/{user}/{repo}@{branch}/{path}',
        }

        if branch is None:
            branch = self.make_default_branch()
        else:
            #  strip '@'
            branch = branch[1:]

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

    def parse_shortcut_repo_url(self, repo_url):
        """
        If repo_url is a shortcut specifying to use local git repo remote url,
        convert repo shortcut to url.

            md2zhihu --repo .                   # default remote, default branch
            md2zhihu --repo .@brach             # default remote
            md2zhihu --repo remote@brach

        """

        elts = repo_url.split('@', 1)
        first = elts.pop(0)
        g = k3git.Git(k3git.GitOpt(), cwd='.')

        is_shortcut = False

        # ".": use cwd git
        # ".@foo_branch": use cwd git and specified branch
        if first == '.':
            msg("Using current git to store assets...")

            u = self.get_remote_url()
            is_shortcut = True

        elif g.remote_get(first) is not None:

            msg("Using current git remote: {} to store assets...".format(first))
            u = self.get_remote_url(first)
            is_shortcut = True

        if is_shortcut:

            if len(elts) > 0:
                u += '@' + elts[0]
            msg("Parsed shortcut {} to {}".format(repo_url, u))
            repo_url = u

        return repo_url

    def get_remote_url(self, remote=None):

        g = k3git.Git(k3git.GitOpt(), cwd='.')

        if remote is None:
            branch = g.head_branch(flag='x')
            remote = g.branch_default_remote(branch, flag='x')

        remote_url = g.remote_get(remote, flag='x')
        return remote_url

    def make_default_branch(self):

        cwd = os.getcwd().split(os.path.sep)
        cwdmd5 = hashlib.md5(to_bytes(os.getcwd())).hexdigest()
        branch = '_md2zhihu_{tail}_{md5}'.format(
            tail=cwd[-1],
            md5=cwdmd5[:8],
        )
        # escape special chars
        branch = re.sub(r'[^a-zA-Z0-9_\-=]+', '', branch)

        return branch


simple_features = dict(
    image=image_local_to_remote,
    math_block=math_block_to_jpg,
    math_inline=math_inline_to_jpg,
    table=table_to_jpg,
    codespan=to_plaintext,
    block_code=dict(
        mermaid=block_code_mermaid_to_jpg,
        graphviz=block_code_graphviz_to_jpg,
        **{"": block_code_to_jpg,
           "*": block_code_to_fixwidth_jpg,
           },
    )
)

wechat_features = dict(
    image=image_local_to_remote,
    math_block=math_block_to_imgtag,
    math_inline=math_inline_to_imgtag,
    table=table_to_barehtml,
    block_code=dict(
        mermaid=block_code_mermaid_to_jpg,
        graphviz=block_code_graphviz_to_jpg,
        **{"": block_code_to_jpg,
           "*": block_code_to_fixwidth_jpg,
           },
    )
)

zhihu_features = dict(
    image=image_local_to_remote,
    math_block=math_block_to_imgtag,
    math_inline=math_inline_to_imgtag,
    table=table_to_barehtml,
    block_code=dict(
        mermaid=block_code_mermaid_to_jpg,
        graphviz=block_code_graphviz_to_jpg,
    )
)

#  jekyll theme: minimal mistake
minimal_mistake_features = dict(
    image=image_local_to_remote,
    block_code=dict(
        mermaid=block_code_mermaid_to_jpg,
        graphviz=block_code_graphviz_to_jpg,
    )
)


# type, subtype... action
#
all_features = dict(
    image=dict(local_to_remote=image_local_to_remote, ),
    math_block=dict(
        to_imgtag=math_block_to_imgtag,
        to_jpg=math_block_to_jpg,
    ),
    math_inline=dict(
        to_imgtag=math_inline_to_imgtag,
        to_jpg=math_inline_to_jpg,
        to_plaintext=math_inline_to_plaintext,
    ),
    table=dict(
        to_barehtml=table_to_barehtml,
        to_jpg=table_to_jpg,
    ),
    codespan=dict(to_text=to_plaintext),
    block_code=dict(
        graphviz=dict(
            to_jpg=block_code_graphviz_to_jpg,
        ),
        mermaid=dict(
            to_jpg=block_code_mermaid_to_jpg,
        ),
        **{"": dict(to_jpg=block_code_to_jpg),
           "*": dict(to_jpg=block_code_to_fixwidth_jpg),
           },
    )
)


def rules_to_features(rules):
    features = {}
    for r in rules:
        rs, act = r.split(":")
        rs = rs.split("/")

        f = all_features
        rst = features
        for typ in rs[:-1]:
            f = f[typ]
            if typ not in rst:
                rst[typ] = {}

            rst = rst[typ]

        typ = rs[-1]
        rst[typ] = f[typ][act]

    return features


#  features: {typ:action(), typ2:{subtyp:action()}}
def render_with_features(mdrender, n, ctx=None, features=None):
    typ = n['type']

    f = features

    if typ not in f:
        return None

    f = f[typ]
    if callable(f):
        return f(mdrender, n, ctx=ctx)

    #  subtype is info
    lang = n['info'] or ''

    if lang in f:
        return f[lang](mdrender, n, ctx=ctx)

    if '*' in f:
        return f['*'](mdrender, n, ctx=ctx)

    return None


class Config(object):

    #  TODO refactor var names
    def __init__(self,
                 src_path,
                 platform,
                 output_dir,
                 asset_output_dir,
                 asset_repo_url=None,
                 md_output_path=None,
                 code_width=1000,
                 keep_meta=None,
                 ref_files=None,
                 jekyll=False,
                 rewrite=None,
                 ):
        """
        Config of markdown rendering

        Args:
            src_path(str): path to markdown to convert.

            platform(str): target platform the converted markdown compatible with.

            output_dir(str): the output dir path to which converted/generated file saves.

            asset_repo_url(str): url of a git repo to upload output files, i.e.
                    result markdown, moved image or generated images.

            md_output_path(str): when present, specifies the path of the result markdown or result dir.

            code_width(int): the result image width of code block.

            keep_meta(bool): whether to keep the jekyll meta file header.

        """
        self.output_dir = output_dir
        self.md_output_path = md_output_path
        self.platform = platform
        self.src_path = src_path


        self.code_width = code_width
        if keep_meta is None:
            keep_meta = False
        self.keep_meta = keep_meta

        if ref_files is None:
            ref_files = []
        self.ref_files = ref_files

        self.jekyll = jekyll

        if rewrite is None:
            rewrite = []
        self.rewrite = rewrite

        fn = os.path.split(self.src_path)[-1]

        trim_fn = re.match(r'\d\d\d\d-\d\d-\d\d-(.*)', fn)
        if trim_fn:
            trim_fn = trim_fn.groups()[0]
        else:
            trim_fn = fn

        if not self.jekyll:
            fn = trim_fn

        self.article_name = trim_fn.rsplit('.', 1)[0]

        self.asset_output_dir = pjoin(asset_output_dir, self.article_name)
        self.rel_dir = os.path.relpath(self.asset_output_dir, self.output_dir)

        assert(self.md_output_path is not None)

        if self.md_output_path.endswith('/'):
            self.md_output_base = self.md_output_path
            self.md_output_path = pjoin(self.md_output_path, fn)
        else:
            self.md_output_base = os.path.split(
                os.path.abspath(self.md_output_path))[0]

        if asset_repo_url is None:
            self.asset_repo = LocalRepo(self.md_output_path, self.output_dir)
        else:
            self.asset_repo = AssetRepo(asset_repo_url)

        for k in (
            "src_path",
            "platform",
            "output_dir",
            "asset_output_dir",
            "md_output_base",
            "md_output_path",
        ):
            msg(darkyellow(k), ": ",  getattr(self, k))

    def img_url(self, fn):
        url = self.asset_repo.path_pattern.format(
            path=pjoin(self.rel_dir, fn))

        for (pattern, repl) in self.rewrite:
            url = re.sub(pattern, repl, url)

        return url

    def push(self):
        x = dict(cwd=self.output_dir)

        git_path = pjoin(self.output_dir, '.git')
        has_git = os.path.exists(git_path)

        cmdpass('git', 'init', **x)
        cmdpass('git', 'add', '.', **x)
        cmdpass('git',
                '-c', "user.name='drmingdrmer'",
                '-c',  "user.email='drdr.xp@gmail.com'",
                'commit', '--allow-empty',
                '-m', 'by md2zhihu by drdr.xp@gmail.com',
                **x)
        cmdpass('git', 'push', '-f', self.asset_repo.url,
                'HEAD:refs/heads/' + self.asset_repo.branch, **x)

        if not has_git:
            msg("Removing tmp git dir: ", self.output_dir + '/.git')
            shutil.rmtree(self.output_dir + '/.git')


def convert_md(conf, handler=None):

    os.makedirs(conf.output_dir, exist_ok=True)
    os.makedirs(conf.asset_output_dir, exist_ok=True)
    os.makedirs(conf.md_output_base, exist_ok=True)

    with open(conf.src_path, 'r') as f:
        cont = f.read()

    cont, meta, meta_text = extract_jekyll_meta(cont)
    cont, article_refs = extract_ref_definitions(cont)

    refs = {}

    for ref_path in conf.ref_files:
        fcont = fread(ref_path)
        y = yaml.safe_load(fcont)
        for r in y.get('universal', []):
            refs.update(r)
        for r in y.get(conf.platform, []):
            refs.update(r)


    meta_refs = build_refs(meta)
    refs.update(meta_refs)

    refs.update(article_refs)

    parse_to_ast = new_parser()
    ast = parse_to_ast(cont)

    #  with open('ast', 'w') as f:
    #      f.write(pprint.pformat(ast))

    # TODO use feature detection to decide if we need to convert table to hml
    if conf.platform == 'minimal_mistake':
        #  jekyll output does render table well.
        pass
    else:
        fix_tables(ast)

    #  with open('fixed-table', 'w') as f:
    #      f.write(pprint.pformat(ast))

    used_refs = replace_ref_with_def(ast, refs)

    # extract already inlined math
    ast = parse_math(ast)

    #  with open('after-math-1', 'w') as f:
    #      f.write(pprint.pformat(ast))

    # join cross paragraph math
    join_math_block(ast)
    ast = parse_math(ast)

    #  with open('after-math-2', 'w') as f:
    #  f.write(pprint.pformat(ast))

    if handler is None:
        mdr = MDRender(conf, platform=conf.platform)
    else:
        mdr = MDRender(conf, platform=handler)

    out = mdr.render(ast)

    if conf.keep_meta:
        out = ['---', meta_text, '---'] + out

    out.append('')

    ref_list = render_ref_list(used_refs, conf.platform)
    out.extend(ref_list)

    out.append('')

    ref_lines = [
        '[{id}]: {d}'.format(
            id=_id, d=d
        ) for _id, d in used_refs.items()
    ]
    out.extend(ref_lines)

    with open(conf.md_output_path, 'w') as f:
        f.write(str('\n'.join(out)))


def main():

    # TODO refine arg names
    # md2zhihu a.md --output-dir res/ --platform xxx --md-output foo/
    # res/fn.md
    #    /assets/fn/xx.jpg
    #
    # md2zhihu a.md --output-dir res/ --repo a@branch --platform xxx --md-output b.md
    #
    # TODO then test drmingdrmer.github.io with action

    parser = argparse.ArgumentParser(
        description='Convert markdown to zhihu compatible')

    parser.add_argument('src_path', type=str,
                        nargs='+',
                        help='path to the markdown to process')

    parser.add_argument('-o', '--md-output', action='store',
                        help='sepcify output path for converted mds.'
                        ' If the path specified ends with "/", it is treated as output dir, e.g. --md-output foo/ output the converted md to foo/<fn>.md.'
                        ' Otherwise it should be the path to some md file such as a/b/c.md. '
                        ' default: <output-dir>/<fn>.md')

    parser.add_argument('-d', '--output-dir', action='store',
                        default='_md2',
                        help='sepcify directory path to store outputs(default: "_md2")'
                        ' It is the root dir of the git repo for storing assets')

    parser.add_argument('--asset-output-dir', action='store',
                        help='sepcify directory to store assets (default: <output-dir>)'
                        ' If <asset-output-dir> is outside <output-dir>, nothing will be uploaded.')

    parser.add_argument('-r', '--repo', action='store',
                        required=False,
                        help='sepcify the git url to store assets.'
                             ' The url should be in a SSH form such as:'
                             ' "git@github.com:openacid/openacid.github.io.git[@branch_name]".'
                             ' When absent, assets are referenced by relative path and it will not push assets to remote.'
                             ' If no branch is specified, a branch "_md2zhihu_{cwd_tail}_{md5(cwd)[:8]}" is used,'
                             ' in which cwd_tail is the last segment of current working dir.'
                             ' It has to be a public repo and you have the write access.'
                             ' "-r ." to use the git in CWD to store the assets.'
                        )

    parser.add_argument('-p', '--platform', action='store',
                        required=False,
                        default='zhihu',
                        choices=["zhihu", "wechat", "weibo", "simple", "minimal_mistake"],
                        help='convert to a platform compatible format.'
                        ' simple is a special type that it produce simplest output, only plain text and images, there wont be table, code block, math etc.'
                        )

    parser.add_argument('--keep-meta', action='store_true',
                        required=False,
                        default=False,
                        help='if keep meta header, which is wrapped with two "---" at file beginning.'
                        ' default: False'
                        )

    parser.add_argument('--jekyll', action='store_true',
                        required=False,
                        default=False,
                        help='respect jekyll syntax: 1) implies <keep-meta>: do not trim md header meta;'
                        ' 2) keep jekyll style name: YYYY-MM-DD-TITLE.md;'
                        ' default: False'
                        )

    parser.add_argument('--refs', action='append',
                        required=False,
                        help='external file that contains ref definitions'
                        ' A ref file is a yaml contains dict of list.'
                        ' A dict key is the platform name, only visible to <platform> argument'
                        ' "univeral" is visible with any <platform>'
                        ' An example of ref file data:'
                        '  {"universal": [{"grpc":"http:.."}, {"protobuf":"http:.."}],'
                        '   "zhihu": [{"grpc":"http:.."}, {"protobuf":"http:.."}]'
                        '}.'
                        ' default: []'
                        )

    parser.add_argument('--rewrite', action='append',
                        nargs=2,
                        required=False,
                        help='rewrite generated to image url.'
                        ' E.g.: --rewrite "/asset/" "/resource/"'
                        ' will transform "/asset/banner.jpg" to "/resource/banner.jpg"'
                        ' default: []'
                        )

    parser.add_argument('--code-width', action='store',
                        required=False,
                        default=1000,
                        help='specifies code image width.'
                        ' default: 1000'
                        )

    args = parser.parse_args()

    if args.md_output is None:
        args.md_output = args.output_dir + '/'

    if args.asset_output_dir is None:
        args.asset_output_dir = args.output_dir

    if args.jekyll:
        args.keep_meta = True

    msg("Build markdown: ", darkyellow(args.src_path),
        " into ", darkyellow(args.md_output))
    msg("Build assets to: ", darkyellow(args.asset_output_dir))
    msg("Git dir: ", darkyellow(args.output_dir))
    msg("Gid dir will be pushed to: ", darkyellow(args.repo))

    for path in args.src_path:

        #  TODO Config should accept only two arguments: the path and a args
        conf = Config(
            path,
            args.platform,
            args.output_dir,
            args.asset_output_dir,
            asset_repo_url=args.repo,
            md_output_path=args.md_output,
            code_width=args.code_width,
            keep_meta=args.keep_meta,
            ref_files=args.refs,
            jekyll=args.jekyll,
            rewrite=args.rewrite,
        )

        convert_md(conf)

        msg(sj("Done building ", darkyellow(conf.md_output_path)))

    if conf.asset_repo.is_local:
        msg("No git repo specified")
    else:
        msg("Pushing ", darkyellow(conf.output_dir), " to ", darkyellow(
            conf.asset_repo.url), " branch: ", darkyellow(conf.asset_repo.branch))
        conf.push()

    msg(green(sj("Great job!!!")))


if __name__ == "__main__":
    main()
