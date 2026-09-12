import matplotlib.pyplot as plt


def create_horizontal_bar_graph(
    category_scores,
    title="Overall Scores"
):

    categories = list(category_scores.keys())
    scores = list(category_scores.values())

    if not category_scores:
        raise ValueError("At least one category score is required")

    # Individual colors for each category
    colors = [
        "#2E7D32",  # Openness - Green
        "#1565C0",  # Conscientiousness - Blue
        "#FB8C00",  # Extraversion - Orange
        "#7B1FA2",  # Agreeableness - Purple
        "#D32F2F",  # Neuroticism - Red

        "#00897B",  # Analytical Thinking - Teal
        "#6D4C41",  # Problem Solving - Brown
        "#3949AB",  # Logical Reasoning - Indigo
        "#F4511E",  # Leadership - Deep Orange

        "#43A047",  # Ethical Integrity - Green
        "#E53935",  # Digital Addiction - Red
        "#8E24AA",  # Level of Overthinking - Purple
        "#039BE5"   # Team Collaboration - Light Blue
    ]

    colors = [colors[index % len(colors)] for index in range(len(categories))]

    # Reverse everything so first category stays at the top
    categories = categories[::-1]
    scores = scores[::-1]
    colors = colors[::-1]

    # Create figure
    fig, ax = plt.subplots(figsize=(11, 9))

    # Create horizontal bars with individual colors
    bars = ax.barh(
        categories,
        scores,
        color=colors
    )

    # Score range
    ax.set_xlim(0, 100)

    # X-axis ticks
    ax.set_xticks([
        0,
        20,
        40,
        60,
        80,
        100
    ])

    # Title
    # ax.set_title(
    #     title,
    #     fontsize=18,
    #     fontweight="bold",
    #     loc="left",
    #     pad=20
    # )

    # Add score at the end of every bar
    for bar, score in zip(bars, scores):

        ax.text(
            score + 2,
            bar.get_y() + bar.get_height() / 2,
            f"{score:.0f}",
            va="center",
            fontsize=10,
            fontweight="bold"
        )

    # Remove unnecessary borders
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Grid
    ax.grid(
        axis="x",
        linestyle="--",
        alpha=0.3
    )

    plt.tight_layout()

    # Save graph
    plt.savefig(
        "overall_scores.png",
        dpi=150,
        bbox_inches="tight"
    )

    return fig