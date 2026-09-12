import io
import matplotlib.pyplot as plt
from .demographbargraph import create_horizontal_bar_graph
from .demographpolygon import create_polygon_graph

import numpy as np


def generate_personality_graphs(questions):
    """
    Calls both graph functions and stores the generated
    images in memory buffers.

    Args:
    questions (list):
        List containing exactly 36 ratings, each expected
        to be between 1 and 5.

    Returns:
        dict:
            Dictionary containing both image buffers.
    """

    if len(questions) != 36:
        raise ValueError("Exactly 36 ratings are required.")
    if any(not isinstance(score, (int, float)) or not 1 <= score <= 5 for score in questions):
        raise ValueError("Personality ratings must be numbers between 1 and 5.")

    category_mapping = {
        "Openness": (0, 3),                 # Q1-Q3
        "Conscientiousness": (3, 6),        # Q4-Q6
        "Extraversion": (6, 9),             # Q7-Q9
        "Agreeableness": (9, 12),           # Q10-Q12
        "Emotional Stability": (12, 15),    # Q13-Q15
        "Leadership": (15, 18),             # Q16-Q18
        "Analytical Thinking": (18, 21),    # Q19-Q21
        "Problem Solving": (21, 24),        # Q22-Q24
        "Learning Agility": (24, 27),       # Q25-Q27
        "Digital Adaptability": (27, 30),   # Q28-Q30
        "Ethical Integrity": (30, 33),      # Q31-Q33
        "Team Collaboration": (33, 36)      # Q34-Q36
    }

    category_scores = {}

    for category, (start, end) in category_mapping.items():

        # Get the ratings belonging to this category
        category_ratings = questions[start:end]

        # Calculate mean
        mean_score = np.mean(category_ratings)

        # Convert 1-5 scale to 0-100 scale
        percentage_score = (mean_score / 5) * 100

        category_scores[category] = round(percentage_score, 2)

    # Create both graphs
    polygon_fig = create_polygon_graph(
        category_scores,
        title="Personality Assessment"
    )

    bar_fig = create_horizontal_bar_graph(
        category_scores,
        title="Overall Scores"
    )

    # Create in-memory buffers
    polygon_buffer = io.BytesIO()
    bar_buffer = io.BytesIO()

    # Save figures into buffers
    polygon_fig.savefig(
        polygon_buffer,
        format="png",
        bbox_inches="tight"
    )

    bar_fig.savefig(
        bar_buffer,
        format="png",
        bbox_inches="tight"
    )

    plt.close(polygon_fig)
    plt.close(bar_fig)

    # Move pointer to beginning
    polygon_buffer.seek(0)
    bar_buffer.seek(0)

    return {
        "polygon": polygon_buffer,
        "horizontal_bar": bar_buffer
    }


def delete_graph_buffers(graph_buffers):
    """
    Deletes/clears all graph image buffers.

    Args:
        graph_buffers (dict):
            Dictionary returned by generate_personality_graphs().
    """

    for buffer in graph_buffers.values():
        buffer.close()