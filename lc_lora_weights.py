"""Shared row weights for direct loading, stacks and saved image metadata."""

import math


def row_strengths(row):
    def number(value):
        try:
            result = float(value)
            return result if math.isfinite(result) else 0.0
        except (TypeError, ValueError):
            return 0.0

    model = number(row.get('strength', 1.0))
    clip = model if row.get('strengthTwo') is None else number(row['strengthTwo'])
    return model, clip
