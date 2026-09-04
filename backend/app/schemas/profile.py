"""추천 엔진 입력. 질문 답변에서 변환되거나 API로 직접 받는다."""

from pydantic import Field

from .common import CamelModel


class BeneficiaryProfile(CamelModel):
    age: int | None = Field(default=None, ge=0, le=130, description="만 나이")
    region: str | None = Field(default=None, description="예: 서울특별시, 경기도")
    living_alone: bool | None = None
    basic_livelihood_recipient: bool | None = Field(default=None, description="기초생활보장 수급")
    medical_aid_recipient: bool | None = Field(default=None, description="의료급여 수급")
    near_poverty_status: bool | None = Field(default=None, description="차상위계층")
    basic_pension_recipient: bool | None = Field(default=None, description="기초연금 수급")
    registered_disabled: bool | None = None
    income_information_complete: bool = Field(
        default=False,
        description="false이면 소득자격 불일치를 탈락이 아니라 확인 필요로 남긴다",
    )
    income_types: list[str] = Field(default_factory=list, description="이미 알고 있는 소득자격 코드")
    needs: list[str] = Field(default_factory=list, description="필요 분류 코드 (CARE, MEAL ...)")
    assistance_need: list[str] = Field(default_factory=list, description="LOW, MEDIUM, HIGH")
    tags: list[str] = Field(default_factory=list, description="생활상황 태그 (LIVING_ALONE ...)")
