"""`data/manifest.json`과 부서별 JSON을 읽어 메모리 카탈로그를 만든다.

`frontend/welfare-search.js`의 `loadWelfareCatalog`와 같은 검증을 수행한다.
"""

import json
from pathlib import Path

from pydantic import ValidationError

from app.schemas.catalog import Department, Manifest
from app.schemas.program import WelfareProgram


class CatalogError(RuntimeError):
    """데이터 파일이 없거나 매니페스트와 어긋날 때."""


class WelfareCatalog:
    def __init__(self, manifest: Manifest, departments: list[Department], programs: list[WelfareProgram]):
        self.manifest = manifest
        self.departments = departments
        self.programs = programs
        self._by_id = {program.id: program for program in programs}

    def get(self, program_id: str) -> WelfareProgram | None:
        return self._by_id.get(program_id)

    def __len__(self) -> int:
        return len(self.programs)


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise CatalogError(f"데이터 파일을 찾을 수 없습니다: {path}")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CatalogError(f"JSON 파싱 실패: {path} ({exc})") from exc


def load_catalog(data_dir: Path) -> WelfareCatalog:
    manifest_path = data_dir / "manifest.json"
    try:
        manifest = Manifest.model_validate(_read_json(manifest_path))
    except ValidationError as exc:
        raise CatalogError(f"매니페스트 형식 오류: {exc}") from exc

    departments: list[Department] = []
    programs: list[WelfareProgram] = []

    for entry in manifest.departments:
        document = _read_json(data_dir / entry.file)
        department = document.get("department") or {}
        raw_programs = document.get("programs")
        if not isinstance(raw_programs, list) or not department.get("id"):
            raise CatalogError(f"잘못된 부서 데이터: {entry.file}")
        if department["id"] != entry.id:
            raise CatalogError(
                f"매니페스트 부서 ID({entry.id})와 JSON 부서 ID({department['id']})가 다릅니다."
            )

        department_name = department.get("name", entry.name)
        departments.append(
            Department(
                id=entry.id,
                name=department_name,
                scope=department.get("scope"),
                program_count=len(raw_programs),
            )
        )
        for raw in raw_programs:
            try:
                programs.append(
                    WelfareProgram.model_validate(
                        {**raw, "departmentId": entry.id, "departmentName": department_name}
                    )
                )
            except ValidationError as exc:
                raise CatalogError(f"{entry.file}의 사업 {raw.get('id', '?')} 형식 오류: {exc}") from exc

    ids = [program.id for program in programs]
    if len(set(ids)) != len(ids):
        raise CatalogError("중복된 복지사업 ID가 있습니다.")
    expected = manifest.dataset.record_count
    if expected is not None and expected != len(programs):
        raise CatalogError(f"매니페스트 건수({expected})와 실제 건수({len(programs)})가 다릅니다.")

    return WelfareCatalog(manifest, departments, programs)
