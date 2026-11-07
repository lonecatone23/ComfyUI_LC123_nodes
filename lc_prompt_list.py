"""LC Prompt List: one prompt per line, sent out as a list (every line runs as its own generation). Same inputs and
outputs as CR Prompt List, so the Vision Assistant swap carries everything over. Blank lines are skipped (CR turned
them into a prompt that was only the prepend text), and a line can be switched off with // in front of it."""


def _one(v) -> str:
    if isinstance(v, (list, tuple)):
        return str(v[0]) if v else ""
    return "" if v is None else str(v)


class LCPromptList:
    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "prepend_text": ("STRING", {"default": "", "multiline": False,
                                            "tooltip": "Goes in front of every line, as is. End it with a space or a comma."}),
                "multiline_text": ("STRING", {"default": "", "multiline": True,
                                              "tooltip": "One prompt per line. // in front of a line switches it off."}),
                "append_text": ("STRING", {"default": "", "multiline": False,
                                           "tooltip": "Goes after every line, as is. Start it with a space or a comma."}),
                "start_index": ("INT", {"default": 0, "min": 0, "max": 9999,
                                        "tooltip": "First line to use (0 = the first). Blank and // lines don't count."}),
                "max_rows": ("INT", {"default": 1000, "min": 1, "max": 9999, "tooltip": "How many lines to use from there."}),
                "skip_blank_lines": ("BOOLEAN", {"default": True,
                                                 "tooltip": "On: blank lines and // lines are left out. Off: every line is a prompt, like CR Prompt List."}),
            },
        }

    RETURN_TYPES = ("STRING", "STRING", "INT")
    RETURN_NAMES = ("prompt", "body_text", "count")
    OUTPUT_IS_LIST = (True, True, False)
    OUTPUT_TOOLTIPS = ("Every line with the prepend and append text: one generation each.",
                       "The same lines without the prepend and append text.", "How many prompts go out.")
    FUNCTION = "make_list"
    CATEGORY = "LC123/prompt"
    DESCRIPTION = ("One prompt per line, sent out as a list: every line runs as its own generation. Blank lines and lines "
                   "starting with // are left out. Replaces CR Prompt List (same inputs and outputs).")

    def make_list(self, multiline_text, prepend_text="", append_text="", start_index=0, max_rows=1000, skip_blank_lines=True):
        pre, post = _one(prepend_text), _one(append_text)
        lines = _one(multiline_text).replace("\r\n", "\n").replace("\r", "\n").split("\n")
        if skip_blank_lines:
            lines = [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("//")]
        if not lines:
            lines = [""]
        start = max(0, min(int(start_index), len(lines) - 1))  # past the end: the last line, as CR does
        rows = lines[start:start + max(1, int(max_rows))]
        return ([pre + ln + post for ln in rows], rows, len(rows))


NODE_CLASS_MAPPINGS = {"LCPromptList": LCPromptList}
NODE_DISPLAY_NAME_MAPPINGS = {"LCPromptList": "LC Prompt List 🗒️"}
