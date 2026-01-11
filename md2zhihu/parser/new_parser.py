from .._vendor import mistune


def new_parser():
    rdr = mistune.create_markdown(
        escape=False,
        renderer="ast",
        plugins=["strikethrough", "footnotes", "table"],
    )

    return rdr
