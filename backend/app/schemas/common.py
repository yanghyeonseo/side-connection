from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """JSON은 camelCase, 파이썬은 snake_case를 쓰기 위한 공통 베이스.

    `data/` JSON과 프론트엔드 타입(`frontend/src/types`)이 모두 camelCase이므로
    응답·요청은 alias(camelCase)로 직렬화하고, 코드에서는 snake_case로 접근한다.
    """

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="ignore")
