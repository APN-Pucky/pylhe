import inspect
from dataclasses import fields, is_dataclass
from typing import Any, Union


def dataclass_with_properties_to_dict(obj: object) -> Union[object, dict[Any, Any]]:
    """Custom serialization function of dataclasses including @property values."""
    if is_dataclass(obj):
        result = {}
        # Include real dataclass fields
        for f in fields(obj):
            value = getattr(obj, f.name)
            result[f.name] = dataclass_with_properties_to_dict(value)
        # Include @property values
        for name, _ in inspect.getmembers(type(obj), lambda m: isinstance(m, property)):
            if name not in result:
                try:
                    value = getattr(obj, name)
                    result[name] = dataclass_with_properties_to_dict(value)
                except Exception:
                    pass
        return result
    if isinstance(obj, (list, tuple, set)):
        return type(obj)(dataclass_with_properties_to_dict(v) for v in obj)
    if isinstance(obj, dict):
        return {k: dataclass_with_properties_to_dict(v) for k, v in obj.items()}
    return obj
