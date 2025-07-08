import re

def render_with_latex(text):
    if not text:
        return []

    # Regex patterns
    block_latex_regex = re.compile(r"\$\$([^$]+)\$\$")
    inline_latex_regex = re.compile(r"\$([^$]+)\$")
    bold_regex = re.compile(r"\*\*([^*]+)\*\*")

    # Split by block LaTeX
    block_parts = block_latex_regex.split(text)
    rendered = []

    for block_index, part in enumerate(block_parts):
        if block_index % 2 == 0:
            # Process inline LaTeX within this text part
            inline_parts = inline_latex_regex.split(part)
            for inline_index, inline_part in enumerate(inline_parts):
                if inline_index % 2 == 0:
                    # Process bold text
                    bold_parts = bold_regex.split(inline_part)
                    for bold_index, bold_part in enumerate(bold_parts):
                        if bold_index % 2 == 0:
                            if bold_part:
                                rendered.append({'type': 'text', 'content': bold_part})
                        else:
                            rendered.append({'type': 'bold', 'content': bold_part})
                else:
                    # Inline LaTeX
                    rendered.append({'type': 'inline_latex', 'content': inline_part})
        else:
            # Block LaTeX
            rendered.append({'type': 'block_latex', 'content': part})

    return rendered 