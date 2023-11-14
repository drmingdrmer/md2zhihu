import re
import fnmatch


# Copied and modified from fnmatch.translate
#
# original `fnmatch.translate()` does not produce grouping regex.
#
def translate(pat):
    """Translate a shell PATTERN to a regular expression, with grouping

    There is no way to quote meta-characters.
    """

    # "*"
    STAR = object()

    # "**"
    STAR2 = object()

    def is_star(v):
        return v is STAR or v is STAR2

    def star_to_regex(v):
        # match single path segment, contains no `/`, escaped `\/` is allowed,
        # double escaped is not allowed: `\\/`
        if v is STAR:
            return r'((?:[^/\\]|\\/|\\\\)*?)'

        # match multi path segment
        if v is STAR2:
            return r'(.*?)'

        raise Exception("not star:" + repr(v))

    res = []
    add = res.append
    i, n = 0, len(pat)
    while i < n:
        c = pat[i]
        i = i+1
        if c == '*':

            add(STAR)

            # compress "**", "**..." to "**"
            if len(res) >= 2:
                if res[-1] is STAR:
                    if res[-2] is STAR or res[-2] is STAR2:
                        res.pop()
                        res[-1] = STAR2
        elif c == '?':
            add('.')
        elif c == '[':
            j = i
            if j < n and pat[j] == '!':
                j = j+1
            if j < n and pat[j] == ']':
                j = j+1
            while j < n and pat[j] != ']':
                j = j+1
            if j >= n:
                add('\\[')
            else:
                stuff = pat[i:j]
                if '-' not in stuff:
                    stuff = stuff.replace('\\', r'\\')
                else:
                    chunks = []
                    k = i+2 if pat[i] == '!' else i+1
                    while True:
                        k = pat.find('-', k, j)
                        if k < 0:
                            break
                        chunks.append(pat[i:k])
                        i = k+1
                        k = k+3
                    chunk = pat[i:j]
                    if chunk:
                        chunks.append(chunk)
                    else:
                        chunks[-1] += '-'
                    # Remove empty ranges -- invalid in RE.
                    for k in range(len(chunks)-1, 0, -1):
                        if chunks[k-1][-1] > chunks[k][0]:
                            chunks[k-1] = chunks[k-1][:-1] + chunks[k][1:]
                            del chunks[k]
                    # Escape backslashes and hyphens for set difference (--).
                    # Hyphens that create ranges shouldn't be escaped.
                    stuff = '-'.join(s.replace('\\', r'\\').replace('-', r'\-')
                                     for s in chunks)
                # Escape set operations (&&, ~~ and ||).
                stuff = re.sub(r'([&~|])', r'\\\1', stuff)
                i = j+1
                if not stuff:
                    # Empty range: never match.
                    add('(?!)')
                elif stuff == '!':
                    # Negated empty range: match any character.
                    add('.')
                else:
                    if stuff[0] == '!':
                        stuff = '^' + stuff[1:]
                    elif stuff[0] in ('^', '['):
                        stuff = '\\' + stuff
                    add(f'[{stuff}]')
        else:
            add(re.escape(c))
    assert i == n

    # Deal with STARs.
    inp = res

    res = []
    add = res.append

    i, n = 0, len(inp)
    # Fixed pieces at the start?
    add('(')
    while i < n and not is_star(inp[i]):
        add(inp[i])
        i += 1
    add(')')

    # Now deal with STAR fixed STAR fixed ...
    # For an interior `STAR fixed` pairing, we want to do a minimal
    # .*? match followed by `fixed`, with no possibility of backtracking.
    # Atomic groups ("(?>...)") allow us to spell that directly.
    # Note: people rely on the undocumented ability to join multiple
    # translate() results together via "|" to build large regexps matching
    # "one of many" shell patterns.

    while i < n:
        assert is_star(inp[i])

        star = inp[i]
        i += 1

        if i < n:
            assert not is_star(inp[i])

        fixed = []
        while i < n and not is_star(inp[i]):
            fixed.append(inp[i])
            i += 1

        fixed = "".join(fixed)

        if fixed == '':
            add(star_to_regex(star))
        else:
            add(star_to_regex(star))
            add('(' + fixed + ')')

            #  if i == n:
            #      add("(.*)")
            #      add('(' + fixed + ')')
            #  else:
            #      add(f"(?>(.*?)({fixed}))")

    assert i == n
    res = "".join(res)
    return fr'(?s:{res})\Z'



def fnmap(src_path, src_pattern, dst_pattern):
    """
    Convert path by two fnmatch pattern:

    Given:

    path: foo/x/y.md
    src_pattern: **/*.md
    dst_pattern: **/*-cn.md

    will produce: foo/x/y-cn.md
    """
    regex = translate(src_pattern)

    dst_parts = re.split(r'([*]+)', dst_pattern)

    src_parts = re.split(regex, src_path)

    # strip two empty string produced.
    src_parts = src_parts[1:-1]

    #  (?s:(foo/)(?>(.*?)(/d/))(.*)(\.md))\Z
    #  src_parts:     ['foo/', 'x/y/z', '/d/', 'bar', '.md']
    #  dst_parts: ['bar/', '**', '/d/', '*', '.cn.md']
    #
    #  Replace non-wildcard part with the corresponding one in th edst_parts

    res = []
    for (i, p) in enumerate(src_parts):
        if dst_parts[i] in ('**', '*'):
            res.append(p)
        else:
            res.append(dst_parts[i])

    return ''.join(res)
