"""로그인 없는 세션. 프론트엔드 `createSession`/`saveAnswer`/`getMatches`와 대응."""

from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from .common import CamelModel

UserMode = Literal["self", "helper"]
AnswerValue = str | list[str]


class SessionCreate(CamelModel):
    mode: UserMode = Field(default="self", description="self=본인, helper=보호자")
    helper_type: str | None = Field(default=None, description="자녀·가족, 요양보호사·활동지원사 등")


class SessionCreated(CamelModel):
    session_id: str
    mode: UserMode
    expires_at: datetime


class AnswerIn(CamelModel):
    model_config = ConfigDict(
        **CamelModel.model_config,
        json_schema_extra={"examples": [{"value": "혼자 살아요"}, {"value": ["기초연금", "생계비 지원"]}]},
    )

    value: AnswerValue = Field(description="단일 선택·입력은 문자열, 복수 선택은 문자열 배열")


class SessionView(CamelModel):
    session_id: str
    mode: UserMode
    helper_type: str | None
    answers: dict[str, AnswerValue]
    guardian_follow_up: list[str] = Field(description="'잘 모르겠어요'로 넘긴 질문 ID. 보호자 보완 목록")
    created_at: datetime
    expires_at: datetime


class SessionMatchRequest(CamelModel):
    answers: dict[str, AnswerValue] | None = Field(
        default=None,
        description="주면 세션 답변에 병합한 뒤 추천한다. 생략하면 저장된 답변만 사용",
    )


class BriefResponse(CamelModel):
    text: str
