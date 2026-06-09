from __future__ import annotations

import html
import math
import shutil
from dataclasses import dataclass
from pathlib import Path

from app.schemas.analysis import AnalysisResponse, ForecastPoint


@dataclass(frozen=True)
class ChartBounds:
    min_value: float
    max_value: float
    width: int = 1000
    height: int = 240
    padding_x: int = 48
    padding_y: int = 28


async def build_pdf_report(analysis: AnalysisResponse) -> bytes:
    html_content = _build_dashboard_html(analysis)
    return await _render_dashboard_pdf(html_content)


async def _render_dashboard_pdf(html_content: str) -> bytes:
    from playwright.async_api import async_playwright

    chrome_path = _resolve_chrome_path()
    if chrome_path is None:
        raise RuntimeError("Google Chrome 실행 파일을 찾을 수 없습니다.")

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=True,
            executable_path=chrome_path,
            args=["--disable-dev-shm-usage", "--no-sandbox"],
        )
        try:
            page = await browser.new_page(viewport={"width": 1280, "height": 1600}, device_scale_factor=1)
            await page.set_content(html_content, wait_until="load")
            await page.emulate_media(media="screen")
            await page.wait_for_timeout(100)
            height = await page.locator("#dashboard-root").evaluate("element => Math.ceil(element.scrollHeight)")
            width = await page.locator("#dashboard-root").evaluate("element => Math.ceil(element.scrollWidth)")
            pdf_bytes = await page.pdf(
                width=f"{max(width, 1200)}px",
                height=f"{max(height + 32, 900)}px",
                print_background=True,
                prefer_css_page_size=True,
                margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
            )
            return pdf_bytes
        finally:
            await browser.close()


def _resolve_chrome_path() -> str | None:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
        shutil.which("msedge"),
        shutil.which("brave"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def _build_dashboard_html(analysis: AnalysisResponse) -> str:
    latest = analysis.result.forecast[-1]
    total_net = latest.cumulative_cashflow
    net_worth = latest.net_worth
    forecast_months = len(analysis.result.forecast)
    summary = html.escape(analysis.result.summary)
    created_at = html.escape(analysis.created_at.isoformat())
    title = html.escape(analysis.title)
    income_svg = _build_dual_area_svg(analysis.result.forecast)
    net_worth_svg = _build_line_svg(analysis.result.forecast)

    return f"""
    <!doctype html>
    <html lang="ko">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <style>
          :root {{
            color: #172033;
            background: #f5f7fb;
            font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
          }}
          * {{ box-sizing: border-box; }}
          body {{ margin: 0; background: #f5f7fb; }}
          #dashboard-root {{
            width: 1280px;
            padding: 24px;
            background: #f5f7fb;
          }}
          .dashboard-column {{
            display: grid;
            gap: 16px;
          }}
          .summary-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 12px;
          }}
          .metric {{
            display: grid;
            gap: 8px;
            padding: 16px;
            border: 1px solid #dbe3ef;
            border-radius: 8px;
            background: #fbfcfe;
          }}
          .metric span {{
            color: #687589;
            font-size: 13px;
            font-weight: 700;
          }}
          .metric strong {{
            font-size: 24px;
          }}
          .summary-band {{
            display: flex;
            gap: 16px;
            justify-content: space-between;
            align-items: center;
            padding: 16px;
            border: 1px solid #d7e3e1;
            border-radius: 8px;
            background: #f2faf8;
          }}
          .summary-band p {{
            margin: 0;
            color: #27364c;
            line-height: 1.6;
            white-space: pre-wrap;
          }}
          .summary-meta {{
            flex-shrink: 0;
            display: grid;
            gap: 6px;
            color: #40516b;
            font-size: 12px;
            font-weight: 700;
            text-align: right;
          }}
          .charts-column {{
            display: grid;
            gap: 16px;
          }}
          .chart-block {{
            padding: 16px;
            border: 1px solid #dbe3ef;
            border-radius: 8px;
            background: #ffffff;
          }}
          .chart-block h2 {{
            margin: 0 0 14px;
            font-size: 17px;
          }}
          .chart-note {{
            margin: 10px 0 0;
            color: #687589;
            font-size: 12px;
          }}
        </style>
      </head>
      <body>
        <main id="dashboard-root">
          <section class="dashboard-column">
            <div class="summary-grid">
              { _metric_card("예상 누적 현금흐름", _format_currency(total_net)) }
              { _metric_card("예측 순자산", _format_currency(net_worth)) }
              { _metric_card("예측 개월", f"{forecast_months}개월") }
            </div>

            <div class="summary-band">
              <p>{summary}</p>
              <div class="summary-meta">
                <span>{title}</span>
                <span>{created_at}</span>
              </div>
            </div>

            <div class="charts-column">
              <div class="chart-block">
                <h2>월별 수입/지출</h2>
                {income_svg}
                <p class="chart-note">수입과 지출의 월별 변화를 비교한 영역 차트입니다.</p>
              </div>
              <div class="chart-block">
                <h2>순자산 추이</h2>
                {net_worth_svg}
                <p class="chart-note">예측 기간 동안의 순자산 변화를 나타냅니다.</p>
              </div>
            </div>
          </section>
        </main>
      </body>
    </html>
    """


def _metric_card(label: str, value: str) -> str:
    return f"""
      <div class="metric">
        <span>{html.escape(label)}</span>
        <strong>{html.escape(value)}</strong>
      </div>
    """


def _build_dual_area_svg(points: list[ForecastPoint]) -> str:
    bounds = _calc_bounds(
        [value for point in points for value in (point.income, point.expense)],
        height=240,
    )
    return _build_svg(
        title="월별 수입/지출",
        points=points,
        bounds=bounds,
        series=[
            ("수입", "#2563eb", "#bfdbfe", [point.income for point in points]),
            ("지출", "#dc2626", "#fecaca", [point.expense for point in points]),
        ],
        kind="area",
    )


def _build_line_svg(points: list[ForecastPoint]) -> str:
    bounds = _calc_bounds([point.net_worth for point in points], height=240)
    return _build_svg(
        title="순자산 추이",
        points=points,
        bounds=bounds,
        series=[("순자산", "#0f766e", "#ccefeb", [point.net_worth for point in points])],
        kind="line",
    )


def _build_svg(
    *,
    title: str,
    points: list[ForecastPoint],
    bounds: ChartBounds,
    series: list[tuple[str, str, str, list[float]]],
    kind: str,
) -> str:
    chart_width = bounds.width
    chart_height = bounds.height
    left = bounds.padding_x
    right = bounds.width - bounds.padding_x
    top = bounds.padding_y
    bottom = bounds.height - bounds.padding_y
    x_positions = _x_positions(len(points), left, right)

    grid_values = _grid_values(bounds.min_value, bounds.max_value)
    grid_lines = []
    for value in grid_values:
        y = _map_y(value, bounds.min_value, bounds.max_value, top, bottom)
        grid_lines.append(
            f'<line x1="{left}" y1="{y:.2f}" x2="{right}" y2="{y:.2f}" stroke="#e8edf5" stroke-width="1" />'
        )
        grid_lines.append(
            f'<text x="12" y="{y + 4:.2f}" fill="#687589" font-size="11">{_format_compact(value)}</text>'
        )

    x_labels = []
    if points:
        label_indices = _label_indices(len(points))
        for index in label_indices:
            x = x_positions[index]
            x_labels.append(
                f'<text x="{x:.2f}" y="{bottom + 18}" fill="#687589" font-size="11" text-anchor="middle">{html.escape(points[index].month)}</text>'
            )

    series_markup = []
    for label, stroke, fill, values in series:
        coords = [
            (x_positions[index], _map_y(value, bounds.min_value, bounds.max_value, top, bottom))
            for index, value in enumerate(values)
        ]
        if kind == "area":
            area_path = _area_path(coords, left, bottom)
            line_path = _line_path(coords)
            series_markup.append(
                f'<path d="{area_path}" fill="{fill}" fill-opacity="0.65" stroke="none" />'
                f'<path d="{line_path}" fill="none" stroke="{stroke}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" />'
            )
        else:
            line_path = _line_path(coords)
            series_markup.append(
                f'<path d="{line_path}" fill="none" stroke="{stroke}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" />'
                + "".join(
                    f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.5" fill="{stroke}" />' for x, y in coords
                )
            )

    legend_items = []
    for label, stroke, _fill, _values in series:
        legend_items.append(
            f'<span style="display:inline-flex;align-items:center;gap:8px;margin-right:14px;">'
            f'<i style="width:10px;height:10px;border-radius:999px;background:{stroke};display:inline-block;"></i>'
            f'<span style="font-size:12px;color:#40516b;font-weight:700;">{html.escape(label)}</span>'
            f"</span>"
        )

    return f"""
      <svg viewBox="0 0 {chart_width} {chart_height + 28}" width="100%" height="{chart_height + 28}" role="img" aria-label="{html.escape(title)}">
        <rect x="0" y="0" width="{chart_width}" height="{chart_height + 28}" fill="#ffffff" rx="8" ry="8" />
        {''.join(grid_lines)}
        <line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#d4dde9" stroke-width="1" />
        {''.join(series_markup)}
        {''.join(x_labels)}
      </svg>
      <div style="display:flex;align-items:center;justify-content:flex-end;gap:8px;margin-top:10px;flex-wrap:wrap;">
        {''.join(legend_items)}
      </div>
    """


def _x_positions(count: int, left: int, right: int) -> list[float]:
    if count <= 1:
        return [float((left + right) / 2)]
    span = right - left
    return [left + span * index / (count - 1) for index in range(count)]


def _line_path(coords: list[tuple[float, float]]) -> str:
    if not coords:
        return ""
    head, *tail = coords
    commands = [f"M {head[0]:.2f} {head[1]:.2f}"]
    commands.extend(f"L {x:.2f} {y:.2f}" for x, y in tail)
    return " ".join(commands)


def _area_path(coords: list[tuple[float, float]], left: int, bottom: int) -> str:
    if not coords:
        return ""
    head, *tail = coords
    commands = [f"M {head[0]:.2f} {bottom:.2f}", f"L {head[0]:.2f} {head[1]:.2f}"]
    commands.extend(f"L {x:.2f} {y:.2f}" for x, y in tail)
    commands.append(f"L {tail[-1][0]:.2f} {bottom:.2f}" if tail else f"L {head[0]:.2f} {bottom:.2f}")
    commands.append("Z")
    return " ".join(commands)


def _calc_bounds(values: list[float], *, height: int) -> ChartBounds:
    if not values:
        return ChartBounds(min_value=0.0, max_value=1.0, height=height)
    min_value = min(values)
    max_value = max(values)
    if math.isclose(min_value, max_value):
        pad = max(1.0, abs(max_value) * 0.1)
        min_value -= pad
        max_value += pad
    else:
        pad = (max_value - min_value) * 0.12
        min_value = max(0.0, min_value - pad)
        max_value += pad
    return ChartBounds(min_value=min_value, max_value=max_value, height=height)


def _map_y(value: float, min_value: float, max_value: float, top: int, bottom: int) -> float:
    span = max(max_value - min_value, 1e-9)
    ratio = (value - min_value) / span
    return bottom - ratio * (bottom - top)


def _grid_values(min_value: float, max_value: float) -> list[float]:
    if math.isclose(min_value, max_value):
        return [min_value]
    return [min_value, (min_value + max_value) / 2, max_value]


def _label_indices(count: int) -> list[int]:
    if count <= 3:
        return list(range(count))
    return [0, count // 2, count - 1]


def _format_currency(value: float) -> str:
    return f"{round(value):,}원"


def _format_compact(value: float) -> str:
    rounded = round(value)
    if abs(rounded) >= 10_000:
        return f"{rounded / 10_000:.1f}만"
    return f"{rounded:,.0f}"
