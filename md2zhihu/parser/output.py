# TODO: move to renderer module?
def render_ref_list(refs, platform):
    ref_lines = ["", "Reference:", ""]
    for ref_id in sorted(refs):
        #  url_and_alt is in form "<url> <alt>"
        url_alt = refs[ref_id].split()
        url = url_alt[0]

        if len(url_alt) == 1:
            txt = ref_id
        else:
            txt = " ".join(url_alt[1:])
            txt = txt.strip('"')
            txt = txt.strip("'")

        ref_lines.append("- {id} : [{url}]({url})".format(id=txt, url=url))

        #  disable paragraph list in weibo
        if platform != "weibo":
            ref_lines.append("")

    return ref_lines
