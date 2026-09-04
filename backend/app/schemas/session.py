"""로그인 없는 세션. 프론트엔드 `createSession`/`saveAnswer`/`getMatches`와 대응."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StringConstraints

from .common import CamelModel

UserMode = Literal["self", "helper"]
# 답변 크기 제한: 자유 입력 남용으로 메모리·AI 프롬프트가 부풀지 않게 한다.
AnswerText = Annotated[str, StringConstraints(max_length=500)]
AnswerValue = AnswerText | Annotated[list[AnswerText], Field(max_length=20)]


class SessionCreate(CamelModel):
    mode: UserMode = Field(default="self", description="self=본인, helper=보호자")
    helper_type: str | None = Field(default=None, description="자녀·가족, 요양보호사·활동지원사 등")


class SessionCreated(CamelModel):
    session_id: str
    case_code: str = Field(description="전화·문자·행정 확인에 쓰는 사례번호")
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
    case_code: str
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


class AdminCase(CamelModel):
    """주민센터·상담원이 사례번호로 여는 행정 확인 화면. `frontend AdminCase` 타입과 1:1."""

    case_code: str
    created_at: str = Field(description="한국 시각 기준 등록 시각 문자열")
    address: str
    household: str
    income_band: str
    public_benefits: str
    family_support: str
    needs: str
    identity_and_account: str
    recommended_benefits: list[str]
    note: str = Field(description="판정 유의사항. AI가 정리하고 실패 시 규칙 기반 문구")


class HelperField(CamelModel):
    """보호자가 대신 채우는 항목. `frontend HelperField` 타입과 1:1."""

    id: str
    label: str
    description: str | None = None
    input: Literal["text", "number"] | None = None
    options: list[str] | None = None
    multiple: bool = Field(default=False, description="true면 options에서 여러 개 선택")


class HelperCase(CamelModel):
    case_code: str
    missing_fields: list[HelperField]


class HelperAnswersIn(CamelModel):
    answers: dict[str, AnswerText] = Field(description="보호자가 채운 값. 키는 HelperField.id")
