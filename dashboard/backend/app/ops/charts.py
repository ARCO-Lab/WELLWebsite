"""Small SVG charts drawn on the server, so welldash²'s pages need no JavaScript or chart library. Hovering a point
or bar shows its value (an SVG <title>). Colours and fonts come from static/ops.css, by class.

An SVG scales its text with its width, so responsive() draws each chart twice, at a desktop and a phone width, and
the stylesheet shows the one that fits the screen."""
import math

from markupsafe import Markup, escape

from utils.timezone import EST_TZ

W, H = 720, 200          # default size, in SVG units
PHONE_W, PHONE_H = 400, 220
LEFT, RIGHT, TOP, BOTTOM = 56, 12, 12, 26


def nice_max(value):
    """A round axis maximum at or above value (1, 2, 2.5 or 5 times a power of ten)."""
    if not value or value <= 0:
        return 1
    power = 10 ** math.floor(math.log10(value))
    for step in (1, 2, 2.5, 5, 10):
        if value <= step * power:
            return step * power
    return 10 * power


def time_label(ts, span_s):
    local = ts.astimezone(EST_TZ)
    return f"{local:%H:%M}" if span_s <= 2 * 86400 else f"{local:%b} {local.day}"


def point_label(ts, span_s):
    local = ts.astimezone(EST_TZ)
    return f"{local:%b} {local.day} {local:%H:%M}" if span_s <= 7 * 86400 else f"{local:%b} {local.day}"


def frame(start, end, top, y_fmt, label, w, h, size):
    """The axes, grid lines and their labels, plus functions mapping a time and a value to SVG coordinates."""
    span = max((end - start).total_seconds(), 1)
    plot_w, plot_h = w - LEFT - RIGHT, h - TOP - BOTTOM

    def x(ts):
        return LEFT + plot_w * min(max((ts - start).total_seconds() / span, 0), 1)

    def y(v):
        return TOP + plot_h * (1 - min(max(v / top, 0), 1))

    parts = [f'<svg class="chart {size}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(label)}">']
    for i in range(5):
        v = top * i / 4
        parts.append(f'<line class="gridline" x1="{LEFT}" x2="{w - RIGHT}" y1="{y(v):.1f}" y2="{y(v):.1f}"/>')
        parts.append(f'<text class="axis" x="{LEFT - 6}" y="{y(v) + 4:.1f}" text-anchor="end">{escape(y_fmt(v))}</text>')
    for i in range(6):
        ts = start + (end - start) * i / 5
        anchor = "start" if i == 0 else "end" if i == 5 else "middle"
        parts.append(f'<text class="axis" x="{x(ts):.1f}" y="{h - 8}" text-anchor="{anchor}">'
                     f'{escape(time_label(ts, span))}</text>')
    return parts, x, y, span


def line_chart(series, start, end, y_fmt=lambda v: f"{v:g}", label="chart", w=W, h=H, size=""):
    """series: [{"name", "cls", "points": [(aware datetime, value or None)]}]. A None value breaks the line."""
    values = [v for s in series for _, v in s["points"] if v is not None]
    top = nice_max(max(values, default=0))
    parts, x, y, span = frame(start, end, top, y_fmt, label, w, h, size)
    for s in series:
        path, pen_down = [], False
        for ts, v in s["points"]:
            if v is None:
                pen_down = False
                continue
            path.append(f"{'L' if pen_down else 'M'}{x(ts):.1f},{y(v):.1f}")
            pen_down = True
        if path:
            parts.append(f'<path class="line {escape(s["cls"])}" d="{" ".join(path)}"/>')
        for ts, v in s["points"]:
            if v is not None:
                parts.append(f'<circle class="dot {escape(s["cls"])}" cx="{x(ts):.1f}" cy="{y(v):.1f}" r="2.5">'
                             f'<title>{escape(s["name"])} {escape(point_label(ts, span))}: {escape(y_fmt(v))}'
                             f'</title></circle>')
    if not values:
        parts.append(f'<text class="empty" x="{w / 2}" y="{h / 2}" text-anchor="middle">No data in this period</text>')
    parts.append("</svg>")
    return Markup("".join(parts))


def bar_chart(points, start, end, step, y_fmt=lambda v: f"{v:g}", label="chart", cls="bar", w=W, h=H, size=""):
    """points: [(bucket start, value)], buckets `step` (a timedelta) wide."""
    top = nice_max(max((v for _, v in points), default=0))
    parts, x, y, span = frame(start, end, top, y_fmt, label, w, h, size)
    for ts, v in points:
        x0, x1 = x(ts), x(ts + step)
        width = max(x1 - x0 - 1, 1)
        parts.append(f'<rect class="{escape(cls)}" x="{x0:.1f}" y="{y(v):.1f}" width="{width:.1f}" '
                     f'height="{max(y(0) - y(v), 0):.1f}"><title>{escape(point_label(ts, span))}: '
                     f'{escape(y_fmt(v))}</title></rect>')
    if not any(v for _, v in points):
        parts.append(f'<text class="empty" x="{w / 2}" y="{h / 2}" text-anchor="middle">No data in this period</text>')
    parts.append("</svg>")
    return Markup("".join(parts))


def responsive(chart, *args, wide=False, **kwargs):
    """The chart at a desktop size (wider for a full-width card) and at a phone size; CSS shows one."""
    desk = chart(*args, w=1200 if wide else W, h=260 if wide else H, size="desk", **kwargs)
    return Markup(desk + chart(*args, w=PHONE_W, h=PHONE_H, size="phone", **kwargs))
