import argparse
import hashlib
import os
import pprint
import re
import shutil
from typing import Optional, List

import k3down2
import k3git
import urllib3
import yaml
from k3color import darkred
from k3color import darkyellow
from k3color import green
from k3handy import cmdpass
from k3handy import pjoin
from k3handy import to_bytes
from k3fs import fread

from .. import mistune

class FrontMatter(object):
    """
    The font matter is the yaml enclosed between `---` at the top of a markdown.
    """
    def __init__(self, front_matter_text: str):
        self.text = front_matter_text
        self.data = yaml.safe_load(front_matter_text)

    def get_refs(self, platform: str) -> dict:
        """
        Get refs from front matter.
        """
        dic = {}

        meta = self.data

        # Collect universal refs
        if 'refs' in meta:
            refs = meta['refs']

            for r in refs:
                dic.update(r)

        # Collect platform specific refs
        if 'platform_refs' in meta:
            refs = meta['platform_refs']
            if platform in refs:
                refs = refs[platform]

                for r in refs:
                    dic.update(r)

        return dic


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


def block_code_to_jpg(mdrender, rnode, width=None):
    n = rnode.node

    txt = code_join(n)

    w = width
    if w is None:
        w = mdrender.conf.code_width

    return typ_text_to_jpg(mdrender, 'code', txt, opt={'html': {'width': w}})


def block_code_to_fixwidth_jpg(mdrender, rnode):
    return block_code_to_jpg(mdrender, rnode, width=600)


def block_code_mermaid_to_jpg(mdrender, rnode):
    n = rnode.node
    return typ_text_to_jpg(mdrender, 'mermaid', n['text'])


def block_code_graphviz_to_jpg(mdrender, rnode):
    n = rnode.node
    return typ_text_to_jpg(mdrender, 'graphviz', n['text'])


def typ_text_to_jpg(mdrender, typ, txt, opt=None):
    d = k3down2.convert(typ, txt, 'jpg', opt=opt)
    fn = asset_fn(txt, 'jpg')
    fwrite(mdrender.conf.asset_output_dir, fn, d)

    return [r'![]({})'.format(mdrender.conf.img_url(fn)), '']


def math_block_to_imgtag(mdrender, rnode):
    n = rnode.node
    return [k3down2.convert('tex_block', n['text'], 'imgtag')]


def math_inline_to_imgtag(mdrender, rnode):
    n = rnode.node
    return [k3down2.convert('tex_inline', n['text'], 'imgtag')]

def math_block_join_dolar_when_nested(mdrender, rnode):

    n = rnode.node

    # If it is not a top level paragraph, convert block math to one-line math.
    # e.g., github does not support multi line block math that is nested in a list item

    # ROOT -> paragraph -> math_block
    # 0       1            2
    if rnode.level > 2:
        return ['$$' + n['text'].strip() + '$$']

    return ['$$', n['text'], '$$']

def math_inline_single_dolar(mdrender, rnode):
    n = rnode.node
    return ['$' + n['text'].strip() + '$']


def math_block_to_jpg(mdrender, rnode):
    n = rnode.node
    return typ_text_to_jpg(mdrender, 'tex_block', n['text'])


def math_inline_to_jpg(mdrender, rnode):
    n = rnode.node
    return typ_text_to_jpg(mdrender, 'tex_inline', n['text'])


def math_inline_to_plaintext(mdrender, rnode):
    n = rnode.node
    return [escape(k3down2.convert('tex_inline', n['text'], 'plain'))]


def to_plaintext(mdrender, rnode):
    n = rnode.node
    return [escape(n['text'])]


def table_to_barehtml(mdrender, rnode) -> List[str]:
    # create a markdown render to recursively deal with images etc.
    mdr = MDRender(mdrender.conf, platform=importer)

    md = mdr.render_node(rnode)
    md = '\n'.join(md)

    table_html = k3down2.convert('table', md, 'html')
    table_html = table_html.split("\n") + ['']
    return table_html


def table_to_jpg(mdrender, rnode):
    mdr = MDRender(mdrender.conf, platform='')

    md = mdr.render_node(rnode)
    md = '\n'.join(md)

    md_base_path = os.path.split(mdrender.conf.src_path)[0]

    return typ_text_to_jpg(mdrender, 'md', md, opt={'html': {
        'asset_base': os.path.abspath(md_base_path),
    }})

def importer(mdrender, rnode):
    '''
    Importer is only used to copy local image to output dir and update image urls.
    This is used to deal with partial renderers, e.g., table_to_barehtml,
    which is not handled by univertial image importer, but need to import the image when rendering a table with images.
    '''

    n = rnode.node

    typ = n['type']

    if typ == 'image':
        return save_image_to_asset_dir(mdrender, rnode)

    return None


def zhihu_specific(mdrender, rnode):
    return render_with_features(mdrender, rnode, features=zhihu_features)

def github_specific(mdrender, rnode):
    return render_with_features(mdrender, rnode, features=github_features)

def minimal_mistake_specific(mdrender, rnode):
    return render_with_features(mdrender, rnode, features=minimal_mistake_features)


def wechat_specific(mdrender, rnode):
    return render_with_features(mdrender, rnode, features=wechat_features)


def weibo_specific(mdrender, rnode):
    n = rnode.node

    typ = n['type']

    if typ == 'image':
        return save_image_to_asset_dir(mdrender, rnode)

    if typ == 'math_block':
        return math_block_to_imgtag(mdrender, rnode)

    if typ == 'math_inline':
        return math_inline_to_plaintext(mdrender, rnode)

    if typ == 'table':
        return table_to_jpg(mdrender, rnode)

    if typ == 'codespan':
        return [escape(n['text'])]

    #  weibo does not support pasting <p> in <li>

    if typ == 'list':
        lines = []
        lines.extend(mdrender.render(rnode))
        lines.append('')
        return lines

    if typ == 'list_item':
        lines = []
        lines.extend(mdrender.render(rnode))
        lines.append('')
        return lines

    if typ == 'block_quote':
        lines = mdrender.render(rnode)
        lines = strip_paragraph_end(lines)
        return lines

    if typ == 'block_code':
        lang = n['info'] or ''
        if lang == 'mermaid':
            return block_code_mermaid_to_jpg(mdrender, rnode)
        if lang == 'graphviz':
            return block_code_graphviz_to_jpg(mdrender, rnode)

        if lang == '':
            return block_code_to_jpg(mdrender, rnode)
        else:
            return block_code_to_jpg(mdrender, rnode, width=600)

    return None


def simple_specific(mdrender, rnode):
    return render_with_features(mdrender, rnode, features=simple_features)


class MDRender(object):
    # platform specific renderer
    platforms = {
        'zhihu': zhihu_specific,
        'github': github_specific,
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

    def render_node(self, rnode):
        """
        Render a AST node into lines of text

        Args:
            rnode is a RenderNode instance
        """

        n = rnode.node
        typ = n['type']

        #  customized renderers:

        lines = self.handlers(self, rnode)
        if lines is not None:
            return lines
        else:
            # can not render, continue with default handler
            pass

        # default renderers:

        if typ == 'thematic_break':
            return ['---', '']

        if typ == 'paragraph':
            lines = self.render(rnode)
            return ''.join(lines).split('\n') + ['']

        if typ == 'text':
            return [n['text']]

        if typ == 'strong':
            lines = self.render(rnode)
            lines[0] = '**' + lines[0]
            lines[-1] = lines[-1] + '**'
            return lines

        if typ == 'math_block':
            return ['$$', n['text'], '$$']

        if typ == 'math_inline':
            return ['$$ ' + n['text'].strip() + ' $$']

        if typ == 'table':
            return self.render(rnode) + ['']

        if typ == 'table_head':
            alignmap = {
                'left': ':--',
                'right': '--:',
                'center': ':-:',
                None: '---',
            }
            lines = self.render(rnode)
            aligns = [alignmap[x['align']] for x in n['children']]
            aligns = '| ' + ' | '.join(aligns) + ' |'
            return ['| ' + ' | '.join(lines) + ' |', aligns]

        if typ == 'table_cell':
            lines = self.render(rnode)
            return [''.join(lines)]

        if typ == 'table_body':
            return self.render(rnode)

        if typ == 'table_row':
            lines = self.render(rnode)
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
            lines = self.render(rnode)
            return add_paragraph_end(lines)

        if typ == 'list_item':
            lines = self.render(rnode)

            # parent is a `list` node
            parent = rnode.parent
            assert parent.node['type'] == 'list'

            head = '-   '
            if parent.node['ordered']:
                head = '1.  '

            lines[0] = head + lines[0]
            lines = lines[0:1] + [indent(x) for x in lines[1:]]
            return lines

        if typ == 'block_text':
            lines = self.render(rnode)
            return ''.join(lines).split('\n')

        if typ == 'block_quote':
            lines = self.render(rnode)
            lines = strip_paragraph_end(lines)
            lines = ['> ' + x for x in lines]
            return lines + ['']

        if typ == 'newline':
            return ['']

        if typ == 'block_html':
            return add_paragraph_end([n['text']])

        if typ == 'link':
            #  TODO title
            lines = self.render(rnode)
            lines[0] = '[' + lines[0]
            lines[-1] = lines[-1] + '](' + n['link'] + ')'

            return lines

        if typ == 'heading':
            lines = self.render(rnode)
            lines[0] = '#' * n['level'] + ' ' + lines[0]
            return lines + ['']

        if typ == 'strikethrough':
            lines = self.render(rnode)
            lines[0] = '~~' + lines[0]
            lines[-1] = lines[-1] + '~~'
            return lines

        if typ == 'emphasis':
            lines = self.render(rnode)
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

    def render(self, rnode) -> List[str]:
        rst = []
        for n in rnode.node['children']:
            child = rnode.new_child(n)
            lines = self.render_node(child)
            rst.extend(lines)

        return rst

    def msg(self, *args):
        msg(*args)


def parse_in_list_tables(nodes) -> List[dict]:
    """
    mistune does not parse table in list item.
    We need to recursively fix it.
    """

    rst = []
    for n in nodes:
        if 'children' in n:
            n['children'] = parse_in_list_tables(n['children'])

        nodes = convert_paragraph_table(n)
        rst.extend(nodes)

    return rst

def convert_paragraph_table(node: dict) -> List[dict]:
    """
    Parse table text in a paragraph and returns the ast of parsed table.

    :return List[dict]: a list of ast nodes.
    """

    if node['type'] != 'paragraph':
        return [node]

    children = node['children']

    if len(children) == 0:
        return [node]

    c0 = children[0]
    if c0['type'] != 'text':
        return [node]

    txt = c0['text']

    table_reg = r' {0,3}\|(.+)\n *\|( *[-:]+[-| :]*)\n((?: *\|.*(?:\n|$))*)\n*'

    match = re.match(table_reg, txt)
    if match:
        mdr = MDRender(None, platform='')
        partialmd = mdr.render(RenderNode(node))
        partialmd = ''.join(partialmd)

        parser = new_parser()
        new_children = parser(partialmd)

        return new_children
    else:
        return [node]



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


def embed(conf, nodes, used_refs):
    """
    Embed the content of url in ![](url) if url matches specified regex
    """

    children = []

    for n in nodes:

        if 'children' in n:
            n['children'] = embed(conf, n['children'], used_refs)

        if n['type'] != 'paragraph' or len(n.get('children', [])) != 1:
            children.append(n)
            continue

        child = n['children'][0]

        if child['type'] != 'image':
            children.append(n)
            continue

        #  {'alt': 'openacid',
        #   'src': 'https://...',
        #   'title': None,
        #   'type': 'image'},

        if not regex_search_any(conf.embed, child['src']):
            children.append(n)
            continue

        article_path = conf.relpath_from_cwd(child['src'])
        md_text = fread(article_path)

        # save and restore parent src_path

        old = conf.src_path
        conf.src_path = article_path

        article = Article(conf, md_text)

        conf.src_path = old

        # rebase urls in embedded article

        child_base = os.path.split(article_path)[0]
        parent_base = os.path.split(conf.src_path)[0]

        new_children = article.ast
        rebase_url_in_ast(conf, child_base, parent_base, new_children)

        children.extend(new_children)

        # update used_refs

        used = {}
        for k,v in article.used_refs.items():
            v = v.strip()
            used[k] = rebase_url(child_base, parent_base,v)

        used_refs.update(used)

    return children


def rebase_url_in_ast(conf, frm, to, nodes):

    for n in nodes:

        if 'children' in n:
            rebase_url_in_ast(conf, frm, to, n['children'])

        if n['type'] == 'image':
            n['src'] = rebase_url(frm, to, n['src'])
            continue

        if n['type'] == 'link':
            n['link'] = rebase_url(frm, to, n['link'])
            continue


def rebase_url(frm, to, src):
    """
    Change relative path based from ``frm`` to from ``to``.
    """
    if re.match(r"http[s]?://", src):
        return src

    if src.startswith('/'):
        return src

    p = os.path.join(frm, src)
    p = os.path.relpath(p, start=to)

    return p



def regex_search_any(regex_list, s):
    for regex in regex_list:
        m = re.search(regex, s)
        if m:
            return True

    return False


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


def extract_math(n):
    """
    Extract ``$$ ... $$`` or ``$ .. $` from a text node and build a new node.
    The original text node is split into multiple segments.

    The math is a block if it is a paragraph.
    Otherwise, it is an inline math.
    """
    children = []

    math_regex = r'([$]|[$][$])([^$].*?)\1'

    t = n['text']
    while True:
        match = re.search(math_regex, t, flags=re.DOTALL)
        if match:
            children.append({'type': 'text', 'text': t[:match.start()]})
            children.append({'type': 'math_inline', 'text': match.groups()[1]})
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


def save_image_to_asset_dir(mdrender, rnode):
    #  {'alt': 'openacid',
    #   'src': 'https://...',
    #   'title': None,
    #   'type': 'image'},

    n = rnode.node

    src = n['src']
    if re.match(r'https?://', src):
        if not mdrender.conf.download:
            return None

        fn = src.split('/')[-1].split('#')[0].split('?')[0]

        content_md5 = hashlib.md5(to_bytes(src)).hexdigest()
        content_md5 = content_md5[:16]
        fn = content_md5 + '-' + fn

        target = pjoin(mdrender.conf.asset_output_dir, fn)

        if not os.path.exists(target):

            http = urllib3.PoolManager()
            r = http.request('GET', src)
            if r.status != 200:
                raise Exception("Failure to download:", src)

            with open(target, 'wb') as f:
                f.write(r.data)

        n['src'] = mdrender.conf.img_url(fn)

        return None

    src = mdrender.conf.relpath_from_cwd(src)

    fn = os.path.split(src)[1]

    with open(src, 'rb') as f:
        content = f.read()

    content_md5 = hashlib.md5(content).hexdigest()
    content_md5 = content_md5[:16]
    fn = content_md5 + '-' + fn

    target = pjoin(mdrender.conf.asset_output_dir, fn)
    shutil.copyfile(src, target)

    n['src'] = mdrender.conf.img_url(fn)

    # Transform ast node but does not render, leave the task to default image
    # renderer.
    return None


def replace_ref_with_def(nodes, refs):
    """
    Convert ``[text][link-def]`` to ``[text](link-url)``
    Convert ``[link-def][]``     to ``[link-def](link-url)``
    Convert ``[link-def]``       to ``[link-def](link-url)``
    """

    used_defs = {}

    for n in nodes:

        if 'children' in n:
            used = replace_ref_with_def(n['children'], refs)
            used_defs.update(used)

        if n['type'] == 'text':
            t = n['text']
            link = re.match(r'^\[(.*?)\](\[([^\]]*?)\])?$', t)
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


def extract_front_matter(cont):
    meta = None
    m = re.match(r'^ *--- *\n(.*?)\n---\n', cont,
                 flags=re.DOTALL | re.UNICODE)
    if m:
        cont = cont[m.end():]
        meta_text = m.groups()[0].strip()
        meta = FrontMatter(meta_text)

    return cont, meta


def render_ref_list(refs, platform):
    ref_lines = ["", "Reference:", ""]
    for ref_id in sorted(refs):

        #  url_and_alt is in form "<url> <alt>"
        url_alt = refs[ref_id].split()
        url = url_alt[0]

        if len(url_alt) == 1:
            txt = ref_id
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


class RenderNode(object):
    """
    RenderNode is a container of current ast-node and parent
    """
    def __init__(self, n, parent=None):
        """
        :param n: ast node: a normal dictionary such as {'type': 'text' ... }
        :param parent: parent RenderNode
        """
        self.node = n

        self.level = 0

        # parent RenderNode
        self.parent = parent

    def new_child(self, n):
        c = RenderNode(n, parent=self)
        c.level = self.level + 1
        return c

    def to_str(self):
        t = "{}".format(self.node.get('type'))
        if self.parent is None:
            return t

        return self.parent.to_str() + " -> " + t

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
            remote = g.branch_default_remote(branch, flag='n')
            if remote is None:
                # `branch` has no remote configured.
                remote = g.cmdf("remote", flag="xo")[0]

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
    image=save_image_to_asset_dir,
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
    image=save_image_to_asset_dir,
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
    image=save_image_to_asset_dir,
    math_block=math_block_to_imgtag,
    math_inline=math_inline_to_imgtag,
    table=table_to_barehtml,
    block_code=dict(
        mermaid=block_code_mermaid_to_jpg,
        graphviz=block_code_graphviz_to_jpg,
    )
)

#  Display markdown in github.com
#  Github supports:
#  - latex math
#  - mermaid
github_features = dict(
    image=save_image_to_asset_dir,
    math_block=math_block_join_dolar_when_nested,
    # github use single dolar inline math.
    math_inline=math_inline_single_dolar,
    block_code=dict(
        graphviz=block_code_graphviz_to_jpg,
    )
)

#  jekyll theme: minimal mistake
minimal_mistake_features = dict(
    image=save_image_to_asset_dir,
    block_code=dict(
        mermaid=block_code_mermaid_to_jpg,
        graphviz=block_code_graphviz_to_jpg,
    )
)

# type, subtype... action
#
all_features = dict(
    image=dict(local_to_remote=save_image_to_asset_dir, ),
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
def render_with_features(mdrender, rnode, features=None):
    n = rnode.node

    typ = n['type']

    f = features

    if typ not in f:
        return None

    f = f[typ]
    if callable(f):
        return f(mdrender, rnode)

    #  subtype is info
    lang = n['info'] or ''

    if lang in f:
        return f[lang](mdrender, rnode)

    if '*' in f:
        return f['*'](mdrender, rnode)

    return None


class ParserConfig(object):
    """
    Config for parsing markdown file.
    """
    def __init__(self):
        pass


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
                 download=False,
                 embed=None,
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
        self.root_src_path = self.src_path

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

        self.download = download
        self.embed = embed or []

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

        assert (self.md_output_path is not None)

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
            msg(darkyellow(k), ": ", getattr(self, k))

    def img_url(self, fn):
        url = self.asset_repo.path_pattern.format(
            path=pjoin(self.rel_dir, fn))

        for (pattern, repl) in self.rewrite:
            url = re.sub(pattern, repl, url)

        return url

    def relpath_from_cwd(self, p):
        """
        If ``p`` starts with "/", it is path starts from CWD.
        Otherwise, it is relative to the md src path.

        :return the path that can be used to read or write.
        """

        if p.startswith('/'):
            # absolute path from CWD.
            p = p[1:]
        else:
            # relative path from markdown containing dir.
            p = os.path.join(os.path.split(self.src_path)[0], p)
            abs_path = os.path.abspath(p)
            p = os.path.relpath(abs_path, start=os.getcwd())

        return p

    def push(self, args, src_dst_fns):
        x = dict(cwd=self.output_dir)

        git_path = pjoin(self.output_dir, '.git')
        has_git = os.path.exists(git_path)

        args_str = '\n'.join([k + ': ' + str(v) for (k, v) in args.__dict__.items()])
        conf_str = '\n'.join([k + ': ' + str(v) for (k, v) in self.__dict__.items()])
        fns_str = '\n'.join([src for (src, dst) in src_dst_fns])

        cmdpass('git', 'init', **x)
        cmdpass('git', 'add', '.', **x)
        cmdpass('git',
                '-c', "user.name='drmingdrmer'",
                '-c', "user.email='drdr.xp@gmail.com'",
                'commit', '--allow-empty',
                '-m', '\n'.join(['Built pages by md2zhihu by drdr.xp@gmail.com',
                                 '',
                                 'CLI args:',
                                 args_str,
                                 '',
                                 'Config:',
                                 conf_str,
                                 '',
                                 'Converted:',
                                 fns_str, ]),
                **x)
        cmdpass('git', 'push', '-f', self.asset_repo.url,
                'HEAD:refs/heads/' + self.asset_repo.branch, **x)

        if not has_git:
            msg("Removing tmp git dir: ", self.output_dir + '/.git')
            shutil.rmtree(self.output_dir + '/.git')


class Article(object):
    def __init__(self, conf: Config, md_text: str):
        self.conf = conf

        # init

        # Input markdown in str
        self.md_text: str = md_text

        # References defined in this markdown
        self.refs = {}

        # References used in this markdown
        self.used_refs = None

        self.front_matter: Optional[FrontMatter] = None

        # Parsed AST of the markdown
        self.ast = None

        # extract article meta

        self.md_text, self.front_matter = extract_front_matter(self.md_text)
        self.md_text, article_refs = extract_ref_definitions(self.md_text)

        # build refs

        self.refs.update(load_external_refs(self.conf))
        if self.front_matter is not None:
            self.refs.update(self.front_matter.get_refs("zhihu"))
        self.refs.update(article_refs)

        # parse to ast and clean up

        parse_to_ast = new_parser()
        self.ast = parse_to_ast(self.md_text)

        self.ast = parse_in_list_tables(self.ast)

        self.used_refs = replace_ref_with_def(self.ast, self.refs)

        # extract already inlined math
        self.ast = parse_math(self.ast)

        # join cross paragraph math
        join_math_block(self.ast)
        self.ast = parse_math(self.ast)

        self.parse_embed()

    def parse_embed(self):
        used_refs = {}
        self.ast = embed(self.conf, self.ast, used_refs)
        self.used_refs.update(used_refs)

    def render(self):

        mdr = MDRender(self.conf, platform=self.conf.platform)

        root_node = {
            'type': 'ROOT',
            'children': self.ast,
        }
        output_lines = mdr.render(RenderNode(root_node))

        if self.conf.keep_meta and self.front_matter is not None:
            output_lines = ['---', self.front_matter.text, '---'] + output_lines

        output_lines.append('')

        ref_list = render_ref_list(self.used_refs, self.conf.platform)
        output_lines.extend(ref_list)

        output_lines.append('')

        ref_lines = [
            '[{id}]: {d}'.format(
                id=ref_id, d=self.used_refs[ref_id]
            ) for ref_id in sorted(self.used_refs)
        ]
        output_lines.extend(ref_lines)

        return output_lines


def load_external_refs(conf: Config) -> dict:
    refs = {}
    for ref_path in conf.ref_files:
        fcont = fread(ref_path)
        y = yaml.safe_load(fcont)
        for r in y.get('universal', []):
            refs.update(r)
        for r in y.get(conf.platform, []):
            refs.update(r)

    return refs


def convert_md(conf):
    os.makedirs(conf.output_dir, exist_ok=True)
    os.makedirs(conf.asset_output_dir, exist_ok=True)
    os.makedirs(conf.md_output_base, exist_ok=True)

    md_text = fread(conf.src_path)

    article = Article(conf, md_text)

    output_lines = article.render()

    with open(conf.md_output_path, 'w') as f:
        f.write(str('\n'.join(output_lines)))

    return conf.md_output_path


class SmartFormatter(argparse.HelpFormatter):

    def _split_lines(self, text, width):
        if text.startswith('R|'):
            return text[2:].splitlines() + ['']
        # this is the RawTextHelpFormatter._split_lines
        return argparse.HelpFormatter._split_lines(self, text, width) + ['']


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
        description='Convert markdown to zhihu compatible',
        formatter_class=SmartFormatter,
    )

    parser.add_argument('src_path', type=str,
                        nargs='+',
                        help='path to the markdowns to convert')

    parser.add_argument('-d', '--output-dir', action='store',
                        default='_md2',
                        help='R|Sepcify dir path to store the outputs.'
                             '\n' 'It is the root dir of the git repo to store the assets referenced by output markdowns.'
                             '\n' 'Deafult: "_md2"'
    )

    parser.add_argument('-o', '--md-output', action='store',
                        help='R|Sepcify output path for converted mds.'
                             '\n' 'If the path specified ends with "/", it is treated as output dir,'
                             ' e.g., "--md-output foo/" output the converted md to foo/<fn>.md.'
                             '\n' 'Default: <output-dir>/<fn>.md')

    parser.add_argument('--asset-output-dir', action='store',
                        help='R|Sepcify dir to store assets'
                             '\n' 'If <asset-output-dir> is outside <output-dir>, nothing will be uploaded.'
                             '\n' 'Default: <output-dir>'
                        )

    parser.add_argument('-r', '--repo', action='store',
                        required=False,
                        help='R|Sepcify the git url to store assets.'
                             '\n' 'The url should be in a SSH form such as:'
                             '\n' '    "git@github.com:openacid/openacid.github.io.git[@branch_name]".'
                             '\n'
                             '\n' 'The repo has to be a public repo and you have the write access.'
                             '\n'
                             '\n' 'When absent, it works in local mode:'
                             ' assets are referenced by relative path and will not be pushed to remote.'
                             '\n'
                             '\n' 'If no branch is specified, a branch "_md2zhihu_{cwd_tail}_{md5(cwd)[:8]}" is used,'
                             ' in which cwd_tail is the last segment of current working dir.'
                             '\n'
                             '\n' '"--repo ." to use the git that is found in CWD'
                        )

    parser.add_argument('-p', '--platform', action='store',
                        required=False,
                        default='zhihu',
                        choices=["zhihu", "github", "wechat", "weibo", "simple", "minimal_mistake"],
                        help='R|Convert to a platform compatible format.'
                             '\n' '"simple" is a special type that it produce simplest output, only plain text and images, there wont be table, code block, math etc.'
                             '\n' 'Default: "zhihu"'
                        )

    parser.add_argument('--keep-meta', action='store_true',
                        required=False,
                        default=False,
                        help='If to keep meta header or not, the header is wrapped with two "---" at file beginning.'
                        )

    parser.add_argument('--jekyll', action='store_true',
                        required=False,
                        default=False,
                        help='R|Respect jekyll syntax:'
                             '\n' '1) It implies <keep-meta>: do not trim md header meta;'
                             '\n' '2) It keep jekyll style file name with the date prefix: YYYY-MM-DD-TITLE.md.'
                        )

    parser.add_argument('--refs', action='append',
                        required=False,
                        help='R|Specify the external file that contains ref definitions.'
                             '\n' 'A ref file is a yaml contains reference definitions in a dict of list.'
                             '\n' 'A dict key is the platform name, only visible when it is enabeld by <platform> argument.'
                             '\n' '"univeral" is visible in any <platform>.'
                             '\n'
                             '\n' 'Example of ref file data:'
                             '\n' '{ "universal": [{"grpc":"http:.."}, {"protobuf":"http:.."}],'
                             '\n' '  "zhihu":     [{"grpc":"http:.."}, {"protobuf":"http:.."}]'
                             '\n' '}.'
                             '\n' 'With an external refs file being specified, in markdown one can just use the ref: e.g., "[grpc][]"'
                        )

    parser.add_argument('--rewrite', action='append',
                        nargs=2,
                        required=False,
                        help='R|Rewrite generated image url.'
                             '\n' 'E.g.: --rewrite "/asset/" "/resource/"'
                             '\n' 'will transform "/asset/banner.jpg" to "/resource/banner.jpg"'
                             '\n' 'Default: []'
                        )

    parser.add_argument('--download', action='store_true',
                        required=False,
                        default=False,
                        help='R|Download remote image url if a image url starts with http[s]://.'
                        )

    parser.add_argument('--embed', action='store',
                        nargs="+",
                        required=False,
                        default=[r'[.]md$'],
                        help='R|Specifies regex of url in `![](url)` to embed.'
                             '\n' 'Example: --embed "[.]md$" will replace ![](x.md) with the content of x.md'
                             '\n' 'Default: ["[.]md$"]'
                        )

    parser.add_argument('--code-width', action='store',
                        required=False,
                        default=1000,
                        help='R|specifies code image width.'
                        '\n' 'Default: 1000'
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

    stat = []
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
            download=args.download,
            embed=args.embed,
        )

        # Check if file exists
        try:
            fread(conf.src_path)
        except FileNotFoundError as e:
            msg(darkred(sj("Warn: file not found: ", repr(conf.src_path))))
            continue

        convert_md(conf)

        msg(sj("Done building ", darkyellow(conf.md_output_path)))

        stat.append([path, conf.md_output_path])

    if conf.asset_repo.is_local:
        msg("No git repo specified")
    else:
        msg("Pushing ", darkyellow(conf.output_dir), " to ", darkyellow(
            conf.asset_repo.url), " branch: ", darkyellow(conf.asset_repo.branch))
        conf.push(args, stat)

    msg(green(sj("Great job!!!")))


if __name__ == "__main__":
    main()
