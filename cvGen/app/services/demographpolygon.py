import matplotlib
import numpy as np

matplotlib.use("Agg")

import matplotlib.pyplot as plt


def create_polygon_graph(category_scores, title="Personality Assessment"):

    categories = list(category_scores.keys())
    values = list(category_scores.values())

    if not categories:
        raise ValueError("At least one category score is required")

    number_of_categories = len(categories)

    # Create angles for the 13 sides
    angles = np.linspace(
        0,
        2 * np.pi,
        number_of_categories,
        endpoint=False
    ).tolist()

    # Close the polygon
    values = values + values[:1]
    angles = angles + angles[:1]

    # Create radar chart
    fig, ax = plt.subplots(
        figsize=(10, 10),
        subplot_kw=dict(polar=True)
    )

    # Start from top
    ax.set_theta_offset(np.pi / 2)

    # Go clockwise
    ax.set_theta_direction(-1)

    # Add category labels
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(
        categories,
        fontsize=8,
        fontweight="bold"
    )

    # Score range
    ax.set_ylim(0, 100)

    ax.set_yticks([20, 40, 60, 80])
    ax.set_yticklabels(["20", "40", "60", "80"])

    # Draw polygon
    ax.plot(
        angles,
        values,
        linewidth=2,
        marker="o"
    )

    # Fill polygon
    ax.fill(
        angles,
        values,
        alpha=0.25
    )

    # # Title
    # plt.title(
    #     title,
    #     fontsize=18,
    #     fontweight="bold",
    #     pad=30
    # )

    return fig