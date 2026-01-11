import re


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
        if "children" in n:
            join_math_block(n["children"])

    join_math_text(nodes)


def parse_math(nodes):
    """
    Extract all math segment such as ``$$ ... $$`` from a text and build a
    math_block or math_inline node.
    """

    children = []

    for n in nodes:
        if "children" in n:
            n["children"] = parse_math(n["children"])

        if n["type"] == "text":
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
        if (
            "children" in n1
            and "children" in n2
            and len(n1["children"]) > 0
            and len(n2["children"]) > 0
            and n1["children"][-1]["type"] == "text"
            and n2["children"][0]["type"] == "text"
            and "$$" in n1["children"][-1]["text"]
        ):
            has_dd = "$$" in n2["children"][0]["text"]
            n1["children"][-1]["text"] += "\n\n" + n2["children"][0]["text"]
            n1["children"].extend(n2["children"][1:])

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

    math_regex = r"([$]|[$][$])([^$].*?)\1"

    t = n["text"]
    while True:
        match = re.search(math_regex, t, flags=re.DOTALL)
        if match:
            children.append({"type": "text", "text": t[: match.start()]})
            children.append({"type": "math_inline", "text": match.groups()[1]})
            t = t[match.end() :]

            left = children[-2]["text"]
            right = t
            if (left == "" or left.endswith("\n\n")) and (right == "" or right.startswith("\n")):
                children[-1]["type"] = "math_block"
            continue

        break
    children.append({"type": "text", "text": t})
    return children
