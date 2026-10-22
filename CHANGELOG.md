# 변경 기록

버전마다 바뀐 동작을 적습니다. 이전 버전에서 옮겨 올 때 확인할 항목은 "호환되지 않는 변경"에 모읍니다. 버전 번호는 커밋마다 올리지 않습니다. 다음 릴리스까지의 변경은 맨 위의 출시 전 절에 더합니다.

## 0.3.0 (출시 전)

첫 공개 릴리스입니다. 0.2.0은 소스의 버전 번호로만 있었고 태그나 릴리스로 배포하지 않았습니다. 0.3.0부터 PyPI와 GitHub 릴리스에 올립니다.

### 호환되지 않는 변경

- CLI의 도움말과 오류 메시지가 한국어에서 영어로 바뀌었습니다. 메시지 문구를 읽는 스크립트는 종료 코드를 보도록 고치세요. 종료 코드의 뜻은 그대로입니다.
- `awkit usage --json`의 결과 형식이 2가 됐습니다. 측정하지 못한 토큰 필드는 `0`이 아니라 `null`이고, 결과에 `format`과 `total.complete`가 붙습니다.
- `awkit review`는 파일 이름, 단계의 `cwd`, `artifacts` 패턴을 명령을 실행한 폴더 기준으로 해석합니다. 저장소 루트에서 실행하면 이전과 같습니다. 하위 폴더에서 실행하면 worktree의 같은 하위 폴더가 기준이 되고, 결과와 manifest에 `subdir`로 남습니다.
- `awkit kit init`과 `awkit kit example`은 만든 폴더를 Git에 commit합니다. 저장소가 없으면 새로 만들고 `core.autocrlf=false`를 설정합니다. 이전처럼 복사만 하려면 `--no-git`을 붙이세요.

### 추가

- `awkit kit example documents|data|analysis`: 결함을 하나 넣은 첫 실행 예제를 만듭니다.
- `awkit kit scan`: 프로젝트의 설정 파일, CI에서 돌리는 검사, 문서 폴더, Git 상태를 보고하고 검사 설정 초안을 냅니다.
- `awkit review check`의 `artifacts`와 `required_artifacts`: 검사한 결과 파일을 해시와 함께 실행 기록에 보존합니다.
- `awkit review verify`, `accept`, `compare`: 보존한 결과를 다시 대조하고, 채택본을 남기고, 다음 실행과 비교합니다.
- `awkit review check HEAD`: 현재 commit을 전체 식별자 없이 검사합니다.
- `awkit usage`: 스레드별 사용자 메시지 수, 명령 수, 경과 시간을 보고합니다.
- `awkit pipeline`: `backup`과 `rollback` 없이 일방향 전달(제출, 업로드)을 설정할 수 있습니다.
- 키트: 작업 유형별 완료 근거(`work-types.md`)와 에이전트 지침의 "Connect the kit to a project" 절을 추가했습니다.

### 수정

- `awkit review`가 저장소가 아닌 폴더에서 저장소를 만들고 `.env`까지 모든 파일을 commit하던 동작을 없앴습니다. 이제 그런 폴더는 거부합니다.
- 이미 commit이 있는 저장소 안에 만든 예제가 commit되지 않아, 예제 README의 첫 명령이 스크립트를 찾지 못하던 문제를 고쳤습니다.
- 스테이징된 변경이 있는 저장소에서 키트를 넣어도 그 변경을 키트 commit에 섞지 않습니다.
- `awkit usage`가 시스템 안내, 명령 출력, 중단 표시를 사용자 메시지로 세던 문제를 고쳤습니다.
- `awkit kit scan`이 `tests` 폴더만 보고 pytest를 제안하던 문제를 고쳤습니다. CI에서 돌리는 명령을 먼저 제안합니다.
- `awkit review accept`를 동시에 두 번 실행하면 채택본이 섞일 수 있던 문제를 잠금으로 막았습니다.
- 저장소 루트에서 `PYTHONPATH=src`로 테스트를 돌리면 일부 테스트가 실패하던 문제를 고쳤습니다.
