import re

def from_rgb_str(color: str) -> tuple[int, int, int]:
    if re.match("#[a-f0-9]{6}$", color):
        return (
            int(color[1:3], 16),
            int(color[3:5], 16),
            int(color[5:7], 16),
        )

    raise ValueError(f"unknown color specifier: {repr(color)}")


def to_rgb_str(color: tuple[int, int, int]):
    return f"#{color[0]:02x}{color[1]:02x}{color[2]:02x}"
