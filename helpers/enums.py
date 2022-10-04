from enum import Enum, EnumMeta


class WSEnum(Enum):
    @classmethod
    def headers(cls: EnumMeta):
        return [x.name for x in cls]

    @classmethod
    def title(cls: EnumMeta):
        return cls.__name__
