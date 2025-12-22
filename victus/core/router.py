from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .schemas import Context, Plan


@dataclass
class RoutedRequest:
    user_input: str
    context: Context
    plan: Optional[Plan]


class Router:
    """Simple request router placeholder.

    Phase 1 only validates that an input/context pair is packaged for planning.
    """

    def route(self, user_input: str, context: Context) -> RoutedRequest:
        if not user_input:
            raise ValueError("user_input must be provided")
        return RoutedRequest(user_input=user_input, context=context, plan=None)
