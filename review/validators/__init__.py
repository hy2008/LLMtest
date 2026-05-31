from abc import ABC, abstractmethod
from typing import List
from review.models import Finding, ReviewContext


class IReviewDimensionValidator(ABC):
    @abstractmethod
    def execute(self, context: ReviewContext) -> List[Finding]:
        ...

    @abstractmethod
    def get_name(self) -> str:
        ...
