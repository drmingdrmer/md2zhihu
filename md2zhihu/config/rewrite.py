"""The rules of --rewrite, --rewrite-if and --rewrite-if-not, which change the URL destinations of the output markdown."""

import re
from dataclasses import dataclass
from typing import Iterable
from typing import Optional
from typing import Sequence
from typing import Union


@dataclass(frozen=True)
class RewriteRule:
    """
    Replace `pattern` in a URL with `repl`, as `re.sub(pattern, repl, url)` does.
    With a `selector`, the rule applies only to a URL in which `re.search(selector, url)` finds a match,
    or, with `negate`, only to a URL in which it finds none.
    """

    pattern: str
    repl: str
    selector: Optional[str] = None
    negate: bool = False

    def apply(self, url: str) -> str:
        if self.selector is not None:
            selected = re.search(self.selector, url) is not None
            if selected == self.negate:
                return url
        return re.sub(self.pattern, self.repl, url)


# A rule, or the two strings of an unconditional rule, [pattern, repl], as the --rewrite flags of earlier versions give.
RuleLike = Union[RewriteRule, Sequence[str]]


def to_rule(rule: RuleLike) -> RewriteRule:
    if isinstance(rule, RewriteRule):
        return rule
    pattern, repl = rule
    return RewriteRule(pattern, repl)


def rewrite_url(rules: Iterable[RuleLike], url: str) -> str:
    """Apply each of `rules` to `url` in order, each to the result of the one before it, and return the result."""
    for rule in rules:
        url = to_rule(rule).apply(url)
    return url
