# Copyright 2022 DoorDash, Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the specific language governing permissions and limitations under the License.


import base64
import math
from io import BytesIO
from typing import Any, Callable, List, Optional, Tuple, Union

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import cm
from matplotlib.pyplot import gca
from pandas.api.types import is_object_dtype

from .data_utils import drop_outliers_iqr


def sparkify(
    plt_func: Callable[..., None],
    figsize: Tuple[float, float] = (3, 0.25),
    ylim: Optional[List[float]] = None,
    caption: Optional[str] = None,
    *args: Any,
    **kwargs: Any,
) -> str:
    """Modify a plot (generated by plot function) for use in table (sparkline style).

    Generates a matplotlib figure with plt_func and:
    * Remove axes, margins
    * Translate to base64-encoded embeddable HTML image text string

    Usage:
        `df.apply(lambda ser: sparkify(robust_hist, ser=ser, figsize=(3, 0.25)))`

    Args:
        plt_func: Function to generate a plot - should modify the active plot
        figsize: Figure Size parameter to pass to :fun:plt.figure
        ylim: Limits of y axis - passed to :fun:set_ylim
        args: additional args to pass to plt_func
        kwargs: additional kwags to pass to plt_func

    Returns:
        Embeddable HTML image text string
    """
    fig = plt.figure(figsize=figsize)
    ax = plt.Axes(fig, [0.0, 0.0, 1.0, 1.0])
    ax.set_axis_off()
    fig.add_axes(ax)
    plt_func(*args, **kwargs)
    if ylim is not None:
        ax.set_ylim(ylim)
    for k, v in ax.spines.items():
        v.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks([])
    plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
    img = BytesIO()
    plt.savefig(img, bbox_inches="tight", pad_inches=0)
    img.seek(0)
    plt.close(fig)
    img_str = f'<img src="data:image/png;base64,{base64.b64encode(img.read()).decode()}"/>'
    if caption is None:
        return img_str
    else:
        return f"<div title='{caption}'>{img_str}</div>"


def robust_hist(
    ser: pd.Series,
    ref_ser: Optional[pd.Series] = None,
    bins: Optional[int] = 50,
    IQR_multiple: int = 3,
    density: bool = True,
    **kwargs: Any,
) -> matplotlib.axes:
    """Generate a histogram after removing outliers."""
    ser = ser.dropna()
    if is_object_dtype(ser):
        ser = ser.astype("category").cat.codes
    ser = pd.to_numeric(ser)
    if ref_ser is None:
        ref_ser = ser
    else:
        if is_object_dtype(ref_ser):
            ref_ser = ref_ser.astype("category").cat.codes
        ref_ser = pd.to_numeric(ref_ser.dropna())
    no_outliers = drop_outliers_iqr(ref_ser.to_frame(name="ser"), IQR_multiple=IQR_multiple)
    n_unique = no_outliers.ser.nunique()
    bins_np = np.histogram_bin_edges(no_outliers["ser"], bins=min(max(n_unique, 1), bins))  # type: ignore
    return ser.hist(bins=bins_np, density=density, **kwargs)


def box_for_spark(ser: pd.Series, ref_ser: Optional[pd.Series] = None) -> None:
    """Generate a boxplot optimized for small plots in tables."""
    ax = gca()
    ser = ser.dropna()
    if is_object_dtype(ser):
        ser = ser.astype("category").cat.codes
    ser = pd.to_numeric(ser).astype(np.float32)
    ax.boxplot(ser, vert=False, widths=0.8, flierprops={"alpha": 0.2, "markersize": 2})
    if ref_ser is not None:
        ax = gca()
        if is_object_dtype(ref_ser):
            ref_ser = ref_ser.astype("category").cat.codes
        ref_ser_clean = pd.to_numeric(ref_ser.dropna()).astype(np.float32)
        if len(ref_ser_clean):
            ax.set_xlim(ref_ser_clean.min(), ref_ser_clean.max())


def missing_heatmap(ser: pd.Series) -> matplotlib.axes:
    """Generate a heatmap of missing data distribution on the table."""
    ser_chunk = ser.groupby(np.floor(np.arange(len(ser)) / (len(ser) / 15))).aggregate(
        lambda x: x.count() * 1.0 / len(x)
    )
    ax = gca()
    ax.bar(
        x=range(len(ser_chunk)),
        width=1,
        height=[1] * len(ser_chunk),
        color=["white" if val == 0.0 else cm.Reds((val + 0.1) / 1.1) for val in 1 - ser_chunk.values],
    )
    return ax


def donut(perc: float, label: Optional[str] = None, color: str = "blue", wedgewidth: float = 1) -> matplotlib.axes:
    """Generate a donut / pie chart."""
    ax = gca()
    if perc == 1.0:
        plt_data = [perc]
        colors = [color]
    elif perc == 0.0:
        plt_data = [1.0]
        colors = ["white"]
    elif 0.0 < perc < 1.0:
        plt_data = [perc, 1 - perc]
        colors = [color, "white"]
    else:
        return ax

    plt.pie(
        plt_data,
        startangle=90,
        counterclock=False,
        wedgeprops=dict(width=wedgewidth, ec="lightgrey", lw=1, alpha=1.0 if perc > 0.0 else 0.5),
        colors=colors,
    )
    plt.text(0, 0, label or "", horizontalalignment="center", verticalalignment="center", fontsize=8)
    return ax


def spark_donut(perc: float, **kwargs: Any) -> str:
    """Build a spark donut."""
    return sparkify(donut, perc=perc, **kwargs)


def spark_hist(ser: pd.Series, **kwargs: Any) -> str:
    """Build a spark histogram."""
    return sparkify(robust_hist, ser=ser, **kwargs)


def spark_box(ser: pd.Series, **kwargs: Any) -> str:
    """Build a spark box-plot."""
    return sparkify(box_for_spark, ser=ser, **kwargs)


def missing_bar(ser: pd.Series) -> matplotlib.axes:
    """Make a missing bar chart.

    Renders a(n):
    * red bar if entire partition is missing.
    * orange bar if partition is partially missing
    * no bar if partition is full
    """
    ax = gca()
    ax.bar(
        width=1,
        x=range(len(ser)),
        height=1 - ser.values,
        alpha=0.1,
        color=cm.tab20c.colors[3],
    )
    ax.bar(
        width=1,
        x=range(len(ser)),
        height=ser.values,
        bottom=1 - ser.values,
        color=[cm.Reds(0.7) if val == 1.0 else cm.Reds(0.1) for val in ser.values],
    )

    return ax


def spark_missing_bar(ser: pd.Series, **kwargs: Any) -> str:
    """Make a spark missing bar chart."""
    return sparkify(missing_bar, ser=ser, ylim=[0, 1], **kwargs)


def spark_missing_heatmap(ser: pd.Series, **kwargs: Any) -> str:
    """Build a spark missing heatmap."""
    return sparkify(missing_heatmap, ser=ser, ylim=[0, 1], **kwargs)


def millify(n: Union[int, float], precision: int = 0) -> str:
    """Humanize number."""
    millnames = ["", "k", "M", "B", "T", "P", "E", "Z", "Y"]
    n = float(n)
    millidx = max(0, min(len(millnames) - 1, int(math.floor(0 if n == 0 else math.log10(abs(n)) / 3))))
    result = "{:.{precision}f}".format(n / 10 ** (3 * millidx), precision=precision)
    return "{0}{dx}".format(result, dx=millnames[millidx])


pd.Series.robust_hist = robust_hist
