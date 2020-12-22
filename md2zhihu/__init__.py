from .. import mistune
import pprint
import yaml
import re
import sys
import os
import shutil

import k3down2
import k3proc



def pad(line):
    if line == '':
        return ''
    return '    ' + line

def para_end(lines):
    #  add blank line to a paragraph block
    if lines[-1] == '':
        return lines

    lines.append('')
    return lines

def strip_para_end(lines):
    #  remove last blank lines
    if lines[-1] == '':
        return strip_para_end(lines[:-1])

    return lines


def render_node(n, ctx=None):

    if n['type'] == 'thematic_break':
        return ['---', '']

    if n['type'] == 'paragraph':
        lines = render(n['children'])
        return ''.join(lines).split('\n') + ['']

    if n['type'] == 'text':
        return [n['text']]

    if n['type'] == 'strong':
        lines = render(n['children'])
        lines[0] = '**' + lines[0]
        lines[-1] = lines[-1] + '**'
        return lines

    #  if n['type'] == 'math_inline':
    #      #  return ['$$' + n['text'] + '$$']
    #      return ['$$ - ' + n['text'] + ' - $$']

    #  if n['type'] == 'math_block':
    #      #  return ['$$' + n['text'] + '$$']
    #      return ['$$ = ' + n['text'] + ' = $$']

    if n['type'] == 'math_block':
        return [k3down2.tex_to_zhihu(n['text'], True)]

    if n['type'] == 'math_inline':
        return [k3down2.tex_to_zhihu(n['text'], False)]

    if n['type'] == 'table':
        return render(n['children']) + ['']

    if n['type'] == 'table_head':
        alignmap = {
                'left': ':--',
                'right': '--:',
                'center': ':-:',
                None: '---',
        }
        lines = render(n['children'])
        aligns = [alignmap[x['align']] for x in n['children']]
        aligns = '| ' + ' | '.join(aligns) + ' |'
        return ['| ' + ' | '.join(lines) + ' |', aligns]

    if n['type'] == 'table_cell':
        lines = render(n['children'])
        return [''.join(lines)]

    if n['type'] == 'table_body':
        return render(n['children'])

    if n['type'] == 'table_row':
        lines = render(n['children'])
        return ['| ' + ' | '.join(lines) + ' |']

    if n['type'] == 'block_code':
        # remove the last \n
        return ['```' + (n['info'] or '')] + n['text'][:-1].split('\n') + ['```', '']

    if n['type'] == 'codespan':
        return [('`' + n['text'] + '`')]

    if n['type'] == 'image':
        if n['title'] is None:
            return ['![{alt}]({src})'.format(**n)]
        else:
            return ['![{alt}]({src} {title})'.format(**n)]

    if n['type'] == 'list':
        head = '-   '
        if n['ordered']:
            head = '1.  '

        lines = render(n['children'], head)
        return para_end(lines)

    if n['type'] == 'list_item':

        lines = render(n['children'])
        # ctx is head passed from list
        lines[0] = ctx + lines[0]
        lines = lines[0:1] + [pad(x) for x in lines[1:]]
        return lines

    if n['type'] == 'block_text':
        lines = render(n['children'])
        return ''.join(lines).split('\n')

    if n['type'] == 'block_quote':
        lines = render(n['children'])
        lines = strip_para_end(lines)
        lines = ['> ' + x for x in lines]
        return lines + ['']

    if n['type'] == 'newline':
        return ['']

    if n['type'] == 'block_html':
        return para_end([n['text']])

    if n['type'] == 'link':
        #  TODO title
        lines = render(n['children'])
        lines[0] = '[' + lines[0]
        lines[-1] = lines[-1] + '](' + n['link'] + ')'

        return lines

    if n['type'] == 'heading':
        lines = render(n['children'])
        lines[0] = '#' * n['level'] + ' ' + lines[0]
        return lines + ['']

    print(n['type'], n.keys())
    pprint.pprint(n)
    return ['***:' + n['type']]

def render(nodes, ctx=None):
    rst = []
    for n in nodes:
        rst.extend(render_node(n, ctx))

    return rst


def parse_math_inline(nodes):
    for n in nodes:
        if 'children' in n:
            parse_math_inline(n['children'])

            children = []
            for subn in n['children']:
                if subn['type'] == 'text':
                    new_children = extract_math(subn)
                    children.extend(new_children)
                else:
                    children.append(subn)

            n['children'] = children

def join_math_block(nodes):

    for n in nodes:

        if 'children' in n:
            join_math_block(n['children'])

    join_math_text(nodes)


def parse_math_block(nodes):

    children = []

    for n in nodes:

        if 'children' in n:
            n['children'] = parse_math_block(n['children'])

        if n['type'] == 'text':
            new_children = extract_math(n, 'math_block')
            children.extend(new_children)
        else:
            children.append(n)

    return children

def join_math_text(nodes):

    i = 0
    while i < len(nodes)-1:
        n1 = nodes[i]
        n2 = nodes[i+1]
        if ('children' in n1
            and 'children' in n2
            and n1['children'][-1]['type'] == 'text'
            and n2['children'][0]['type'] == 'text'
            and '$$' in n1['children'][-1]['text']):

            has_dd = '$$' in n2['children'][0]['text']
            n1['children'][-1]['text'] += '\n\n' + n2['children'][0]['text']
            n1['children'].extend(n2['children'][1:])

            nodes.pop(i+1)
            #  print('joint', nodes)

            if has_dd:
                i+=1
        else:
            i+=1


inline_math = r'\$\$(.*?)\$\$'

def extract_math(n, typ='math_inline'):
    '''
    Extract ``$$ ... $$`` from a text node and build a new node with type ``typ``.
    The original text node is split into two.
    '''
    children = []

    t = n['text']
    while True:
        match = re.search(inline_math, t, flags=re.DOTALL)
        if match:
            children.append({'type': 'text', 'text': t[:match.start()]})
            children.append({'type': 'math_inline', 'text': match.groups()[0]})
            t = t[match.end():]

            l = children[-2]['text']
            r = t
            if (l == '' or l.endswith('\n\n')) and (r=='' or r.startswith('\n')):
                children[-1]['type'] = 'math_block'
            continue

        break
    children.append({'type':'text', 'text':t})
    return children

def import_img(nodes, host_conf, sess, path):

    for n in nodes:

        if 'children' in n:
            import_img(n['children'], host_conf, sess, path)

        #  {'alt': 'openacid',
        #   'src': 'https://tva1.sinaimg.cn/large/0081Kckwly1gls09bbfnij30m8096gnt.jpg',
        #   'title': None,
        #   'type': 'image'},
        if n['type'] == 'image':
            src = n['src']
            if re.match(r'https?://', src):
                continue

            if src.startswith('/'):
                src = src[1:]
            else:
                src = os.path.join(os.path.split(path)[0], src)

            srcfn = os.path.split(src)[1]
            dst = os.path.join(sess['dstdir'], srcfn)
            shutil.copyfile(src, dst)

            url = host_conf['ptn'].format(path=sess['reldir'] + '/' + srcfn, **host_conf)
            n['src'] = url


def render_table(nodes):
    for n in nodes:

        if 'children' in n:
            render_table(n['children'])

        if n['type'] == 'table':
            md = render_node(n)
            md = '\n'.join(md)
            tablehtml = k3down2.mdtable_to_barehtml(md)
            n['type'] = 'block_html'
            n['text'] = tablehtml


def build_refs(meta):
    if meta is not None and 'refs' in meta:
        refs = meta['refs']

        dic = {}
        for r in refs:
            dic.update(r)

        return dic
    return {}

def fill_refs(nodes, refs):
    for n in nodes:

        if 'children' in n:
            fill_refs(n['children'], refs)

        if n['type'] == 'text':
            t = n['text']
            link = re.match(r'\[(.*?)\](\[\])?', t)
            if link:
                txt = link.groups()[0]
                #  print(link, txt)
                #  print(refs)
                if txt in refs:
                    n['type'] = 'link'
                    r = refs[txt]
                    n['link'] = r.split()[0]
                    n['children'] = [{'type': 'text', 'text':txt}]

def extract_text_refs(cont):
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


def parse_githost(sshurl):
    match = re.match(r'git@(.*?):(.*?)/(.*?)\.git$', sshurl)
    if not match:
        raise ValueError('unknown url: {sshurl};'
                         ' A valid one should be like "{tmpl}"'.format(
                                 sshurl=sshurl,
                                 tmpl='git@github.com:myname/myrepo.git'))

    host, user, repo = match.groups()

    #  engines = {
    #          'git@gitee.com:drdrxp/bed.git',
    #          'https://gitee.com/drdrxp/openacid.github.io/raw/rr/importable/zhihu/slimarray/slim.jpg'
    #          'git@github.com:openacid/openacid.github.io.git',
    #          'https://raw.githubusercontent.com/miracleyoo/Markdown4Zhihu/master/Data/完美使用Markdown在知乎编辑内容/image-20191214174243537.png'
    #  }


    hostpat = {
            'github.com': 'https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}',
            'gitee.com': 'https://gitee.com/{user}/{repo}/raw/{branch}/{path}',
    }

    return {
            'ptn':hostpat[host],
            'user': user,
            'repo':repo,
            'branch': 'drdrxp_says_hi',
    }


def main():

    path, sshurl = sys.argv[1], sys.argv[2]

    fn = os.path.split(path)[-1]
    fnm = re.match(r'\d\d\d\d-\d\d-\d\d-(.*)', fn)
    if fnm:
        fn = fnm.groups()[0]
    folder  = fn.rsplit('.', 1)[0]

    xxdir = 'importable'
    output_folder = xxdir + '/zhihu/{folder}'.format(folder=folder)
    #  print(output_folder, fn)
    os.makedirs(output_folder, exist_ok=True)

    with open(path, 'r') as f:
        cont = f.read()

    meta = re.match(r'^ *--- *\n(.*?)\n---\n', cont, flags=re.DOTALL | re.UNICODE)
    if meta:
        cont = cont[meta.end():]
        meta = meta.groups()[0]
        meta = yaml.load(meta)

    refs = build_refs(meta)

    cont, article_refs = extract_text_refs(cont)

    refs.update(article_refs)
    ref_lines = [
            '[{id}]: {d}'.format(
                    id=id, d=d
            ) for id, d in refs.items()
    ]

    rdr = mistune.create_markdown(
        escape=False,
        renderer='ast',
        plugins=['strikethrough', 'footnotes', 'table'],
    )
    ast = rdr(cont)

    #  pprint.pprint(ast)
    #  raise

    fill_refs(ast, refs)

    host_conf = parse_githost(sshurl)
    sess = {
            'reldir': '/zhihu/{folder}'.format(folder=folder), 
            'dstdir': output_folder,
    }
    import_img(ast, host_conf, sess, path)

    render_table(ast)


    # extract already inlined math
    ast = parse_math_block(ast)

    # join cross paragraph math
    join_math_block(ast)
    ast = parse_math_block(ast)

    with open('ooo', 'w') as f:
        f.write(pprint.pformat(ast))

    out = render(ast)

    out.append('')
    out.extend(ref_lines)

    #  print(out)
    with open(os.path.join(output_folder, fn), 'w') as f:
        f.write(str('\n'.join(out)))

    k3proc.command_ex('git', 'init', cwd=xxdir)
    k3proc.command_ex('git', 'add', '.', cwd=xxdir)
    k3proc.command_ex('git', 'commit', '--allow-empty',  '-m', 'Commit by drdrxp', cwd=xxdir)
    k3proc.command_ex('git', 'push', '-f', sshurl, 'HEAD:refs/heads/' + host_conf['branch'], cwd=xxdir)
    shutil.rmtree(xxdir + '/.git')

if __name__ == "__main__":
    main()
