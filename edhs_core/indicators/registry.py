from typing import Dict, List, Type

from .base import BaseIndicator

_REGISTRY: Dict[str, Type[BaseIndicator]] = {}


def register_indicator(cls: Type[BaseIndicator]) -> Type[BaseIndicator]:
    """
    Class decorator to register an indicator.

    Usage:

        @register_indicator
        class MyIndicator(BaseIndicator):
            id = "my_indicator"
            ...
    """

    if not issubclass(cls, BaseIndicator):
        raise TypeError("Only subclasses of BaseIndicator can be registered.")

    if not cls.id or cls.id == "base":
        raise ValueError("Indicator classes must define a non-empty id.")

    if cls.id in _REGISTRY:
        raise ValueError(f"Indicator id '{cls.id}' is already registered.")

    _REGISTRY[cls.id] = cls
    return cls


def get_indicator_registry() -> Dict[str, Type[BaseIndicator]]:
    """Return the internal registry mapping indicator id to class."""

    return dict(_REGISTRY)


def get_indicator_class(indicator_id: str) -> Type[BaseIndicator]:
    """Retrieve an indicator class by id or raise KeyError."""

    try:
        return _REGISTRY[indicator_id]
    except KeyError as exc:
        raise KeyError(f"Unknown indicator id: {indicator_id}") from exc


def list_indicators() -> List[str]:
    """Return a list of registered indicator identifiers."""

    return sorted(_REGISTRY.keys())
