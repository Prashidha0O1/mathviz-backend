from pydantic import BaseModel, Field

class QuestionRequest(BaseModel):
    """
    Pydantic model for the user's question.
    """
    question: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="The mathematical or algorithmic question to visualize.",
    )