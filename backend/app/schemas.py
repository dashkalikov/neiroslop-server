"""Validate the public API boundary before processing a round."""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, StrictInt


class SpinRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    game: Literal['moon', 'temple', 'neon', 'royal', 'ocean', 'goldrush', 'bigbass', 'saloon']
    bet: StrictInt
    requestId: UUID
