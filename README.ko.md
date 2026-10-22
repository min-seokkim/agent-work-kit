# Agent Work Kit

[English](README.md) | 한국어

Agent Work Kit은 에이전트와 개발하기 위한 작업 지침, 한국어 문서 작성 가이드, 검증 도구를 담은 키트입니다.

Markdown 키트로 작업과 인계 방법을 정하고 문서를 작성합니다. `awkit` CLI를 더하면 검토 스냅샷을 만들고, 프로젝트 검사를 실행하며, 검토 메시지를 주고받고 배포 결과를 확인할 수 있습니다.

에이전트 지침과 작업 양식은 영어로, 사용 안내는 한국어로 제공합니다.

## 한국어 문서 작성

[한국어 작성 가이드](kit/korean-writing.md)는 에이전트가 읽기 쉬운 한국어 개발 문서를 쓰도록 작성 순서와 검토 기준을 정합니다. 사실과 조건을 정리하고 영어 초안을 쓴 뒤 자연스러운 한국어로 옮깁니다. 이후 사실, 문장, 전체 흐름을 차례로 검토합니다. 번역투, 추상적인 표현과 명사 나열을 고치는 방법부터 기술 용어와 문서 구조를 다루는 기준까지 담았습니다.

## 개발과 검토

키트를 프로젝트에 넣으면 적용표 한 장을 채웁니다. 빌드 방법, 변경이 제대로 됐는지 판단할 검사, 작업 기록을 둘 위치를 적는 문서입니다. 에이전트는 일을 시작하기 전에 이 문서를 읽고, 작업마다 목표와 고쳐도 되는 파일, 완료를 판단할 검사를 짧게 기록합니다.

변경이 준비되면 `awkit review snapshot`으로 지정한 파일만 담은 Git commit 객체를 만듭니다. 작업 중인 브랜치와 스테이징 상태, 작업 파일은 그대로 남습니다. `awkit review check`는 이 commit을 별도 worktree에 꺼내 프로젝트의 검사 명령을 실행하고 로그를 남깁니다. 다른 에이전트 세션은 같은 commit을 받아 검토합니다. 요청과 응답, 반박은 `awkit channel`로 주고받으며, 응답은 상대가 실제로 보낸 메시지에만 붙일 수 있습니다.

배포 결과를 확인할 때는 `awkit pipeline`을 사용합니다. 프로젝트가 제공하는 현재 버전 확인, 백업, 배포, 검증과 복귀 명령을 호출하고 실제로 어떤 버전이 실행 중인지 확인합니다. 배포 명령이 0으로 끝났어도 이전 버전이 그대로 돌고 있으면 실패로 기록합니다. 단계가 제한 시간을 넘겨 대상의 상태가 불확실해지면, `reconcile`로 확인한 뒤 다음 배포를 진행합니다.

작업을 나눠 맡길 때는 scout, analyst, builder, verifier, writer 다섯 역할을 사용합니다. 위임 지침에는 작업 위험도, 인계 방법과 검토 예산을 정리했습니다. `awkit kit roles`로 사용 환경에 맞는 역할 파일을 만들고, `awkit usage`로 실행 기록의 모델과 토큰을 확인할 수 있습니다.

프로젝트마다 완료 조건을 정하고 사용하는 빌드, 검사와 배포 명령을 연결합니다. 제품이 맡는 기능은 [역할과 범위](docs/scope.md)에, 다음 구현 순서는 [개발 계획](docs/roadmap.md)에 정리했습니다.

## 설치

Windows나 Linux에서 Python 3.11 이상이 필요합니다. 개발하는 프로젝트의 언어는 상관없습니다.

[릴리스](../../releases)에서 wheel을 내려받아 가상환경에 설치하세요.

```powershell
python -m venv .venv
.venv\Scripts\pip install agent_work_kit-0.2.0-py3-none-any.whl
.venv\Scripts\awkit --version
```

Linux에서는 `.venv/bin/` 아래의 같은 실행 파일을 씁니다. 화면 캡처까지 쓰려면 wheel을 `[ui]` 옵션과 함께 설치하고 `python -m playwright install chromium`을 실행하세요. Markdown 키트만 필요하다면 같은 릴리스의 `agent-work-kit-0.2.0.zip`을 프로젝트에 풀면 되고, 이때는 Python이 없어도 됩니다.

## 빠르게 써 보기

프로젝트에 키트를 넣습니다.

```powershell
awkit kit init C:\work\my-project
```

`agent-work-kit/` 폴더가 생깁니다. 같은 이름의 폴더가 이미 있으면 아무것도 건드리지 않고 멈춥니다. `agent-work-kit/templates/project.md`를 채운 뒤 에이전트에게 이렇게 시작을 부탁하세요.

> Before you start, read `agent-work-kit/templates/agent-instructions.md` and the filled-in `agent-work-kit/templates/project.md`. The project's existing rules take precedence.

변경을 고정하고 따로 검사합니다.

```powershell
$snap = awkit review snapshot src/auth.js tests/auth.test.js
awkit review check $snap --config review-checks.toml
```

같은 commit을 다른 세션에 검토해 달라고 요청합니다.

```powershell
awkit channel post main reviewer review --snap $snap --body "권한 검사 변경을 검토해 주세요."
awkit channel wait reviewer request                 # 검토 세션: 답하지 않은 요청을 기다림
awkit channel post reviewer main re --reply-to M-001 --body-file review.md
awkit channel wait main reply M-001                 # 작성 세션: 응답을 기다림
```

두 세션은 현재 폴더의 `.awkit/channel.sqlite3`를 함께 읽습니다. 다른 파일을 쓰려면 양쪽에 같은 `--db`를 지정하세요.

배포 실행기는 JSON 파일만 바꾸는 모의 대상으로 시험할 수 있습니다.

```powershell
awkit pipeline --config examples/local-release/pipeline.toml deploy aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
awkit pipeline --config examples/local-release/pipeline.toml deploy ffffffffffffffffffffffffffffffffffffffff
```

두 번째 버전은 일부러 상태 검사에 실패하게 해 두었습니다. 실행기는 첫 번째 버전으로 되돌린 뒤 결과를 `failed-restored`로 남기고 종료 코드 1을 반환합니다.

## 명령

| 명령 | 하는 일 | 추가로 필요한 것 |
|---|---|---|
| `awkit kit init` | 프로젝트의 새 폴더에 Markdown 키트를 복사합니다. | |
| `awkit kit roles` | 기존 파일을 보존하면서 다섯 역할의 지침과 등급별 모델 설정을 파일로 만듭니다. | |
| `awkit usage` | Claude Code와 Codex 실행 기록을 읽어 스레드별 실제 모델, 호출, 토큰을 모읍니다. | |
| `awkit review` | 고른 변경을 Git commit으로 고정하고, 별도 worktree에서 프로젝트의 검사 명령을 실행합니다. | Git |
| `awkit channel` | 같은 PC의 두 세션이 SQLite 파일로 검토 요청, 응답, 반박을 주고받습니다. | |
| `awkit publish` | 정적 문서 빌드 결과의 링크를 검사하고 진입 페이지를 원자적으로 바꿉니다. 이전 버전으로 되돌릴 수 있습니다. | |
| `awkit ui` | 지정한 화면을 여러 폭으로 캡처해 검토 시트 한 장에 모읍니다. | Playwright와 브라우저 |
| `awkit pipeline` | 배포 명령을 정해진 순서로 실행하고 실제로 실행 중인 버전을 확인합니다. | 프로젝트의 배포 명령 |

## 배포 실행기가 실패를 다루는 방식

| 상황 | `awkit pipeline`의 처리 |
|---|---|
| 배포 명령은 0으로 끝났는데 이전 버전이 계속 실행 중 | 실패로 기록합니다. 검증 명령이 요청한 버전을 보고하고, 돌려준 검사가 모두 통과해야 성공입니다. |
| 배포는 실패했고 자동 복귀는 성공 | `failed-restored`로 기록하고 1로 종료합니다. 실패한 요청이 기록에서 사라지지 않습니다. |
| 단계가 제한 시간을 넘김 | 그 단계와 단계가 띄운 로컬 프로세스를 모두 종료하고 `uncertain`으로 기록합니다. `reconcile`로 대상을 확인하기 전까지 다음 배포를 막습니다. |
| 현재 버전이 이미 검사에 실패하는 중 | 아무것도 바꾸지 않고 멈춥니다. 고친 버전을 올리려면 `--allow-unhealthy-current`를 붙이세요. 이미 고장 난 버전으로 자동 복귀하지는 않습니다. |
| `rollback`을 여러 번 실행 | 검증을 통과했던 버전을 따라 한 단계씩 돌아갑니다. 마지막 두 버전 사이를 오가지 않습니다. |
| 같은 상태 폴더에서 두 번째 실행이 시작됨 | 시작하지 않습니다. |

실행마다 단계별 종료 코드, 걸린 시간, 표준 출력과 오류를 그 실행의 폴더에 남깁니다.

## 검증

배포, 검토와 발행 명령은 모의 프로젝트에서 검사했습니다. 사용량 집계는 실제 Claude Code 기록으로도 확인했습니다. 환경별 결과, 실패 경로와 실제 적용 때 남은 확인 사항은 [검증 범위](docs/validation.md)에 정리했습니다.

## 문서

- [공통 키트 사용법](kit/README.md): 키트를 프로젝트에 적용하고 첫 작업을 진행하는 순서
- [한국어 작성 가이드](kit/korean-writing.md): 한국어 개발 문서의 작성과 검토 지침
- [위임 지침](kit/delegation.md): 언제 맡길지, 역할, 위험도, 강한 호출 예산, 재시도, 측정
- [검토 세션 협업](kit/review-session.md): 메인 세션 옆에 독립 검토 세션을 붙여 일하는 방법
- [CLI 사용법](docs/cli.md): 설치, 역할 파일, 사용량 집계, 검토 채널, 배포 실행기
- [추가 도구](docs/tools.md): 변경본 고정, 격리 검사, 문서 발행, 화면 캡처
- [역할과 범위](docs/scope.md): 제품이 맡는 기능과 확장 기준
- [검증 범위](docs/validation.md): 자동 검사가 다루는 동작과 아직 확인하지 못한 범위
- [개발 계획](docs/roadmap.md): 현재 기능과 다음 구현 순서

## 개발

```powershell
$env:PYTHONPATH = "$PWD\src"
python -m unittest discover -s tests -v
python scripts/build_release.py        # setuptools>=68, wheel 필요
```

브라우저 검사는 Playwright를 설치하고 `AWKIT_UI_TEST=1`을 지정했을 때만 실행합니다. GitHub Actions가 Windows와 Linux, Python 3.11~3.13에서 전체 검사를 돌립니다. 패키지 버전과 같은 태그(예: `v0.2.0`)를 올리면 wheel과 키트 ZIP을 만들어 릴리스에 붙입니다.

## 라이선스

아직 정하지 않았습니다.
