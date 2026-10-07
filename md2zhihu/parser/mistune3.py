import mistune
from mistune.plugins.table import table_in_list
from mistune.plugins.table import table_in_quote


def new_markdown() -> mistune.Markdown:
    """
    Build a mistune 3 parser that returns tokens instead of HTML.
    """

    # mistune registers no name for table_in_list and table_in_quote, so the functions are passed.
    return mistune.create_markdown(
        renderer="ast",
        plugins=["strikethrough", "table", table_in_list, table_in_quote],
    )
