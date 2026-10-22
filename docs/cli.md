# CLI 사용법

`awkit` 명령의 설치와 키트 넣기, 역할 파일 만들기, 사용량 집계, 검토 채널, 배포 실행기를 다룹니다. 변경본 고정과 격리 검사, 문서 발행, 화면 캡처는 [추가 도구](tools.md)에 따로 정리했습니다. Python 없이 규칙과 양식만 쓰려면 [공통 키트 사용법](../kit/README.md)으로 가세요.

제품의 책임 범위는 [역할과 범위](scope.md)에 정리했습니다. 이 문서는 현재 0.2.0 명령을 기준으로 하며, 사용량 수집과 채널의 후속 변경은 [개발 계획](roadmap.md)에서 다룹니다.

## 설치

Windows나 Linux에서 Python 3.11 이상이 필요합니다. `review`는 Git, `ui`는 Playwright와 브라우저를 추가로 쓰고, 나머지 명령은 표준 라이브러리만으로 동작합니다. 개발하는 애플리케이션의 언어는 상관없습니다.

릴리스에서 `agent_work_kit-<버전>-py3-none-any.whl`을 내려받아 가상환경에 설치합니다.

```powershell
python -m venv .venv
.venv\Scripts\pip install .\agent_work_kit-0.2.0-py3-none-any.whl
.venv\Scripts\Activate.ps1
awkit --version
```

`awkit 0.2.0`이 나오면 됩니다. Linux에서는 `.venv/bin/pip`으로 설치하고 `source .venv/bin/activate`로 활성화합니다. 이 문서의 예제는 가상환경을 활성화했다고 보고 `awkit`을 바로 부릅니다. 활성화하지 않았다면 실행 파일의 경로를 앞에 붙이세요.

설치하지 않고 저장소에서 바로 실행할 수도 있습니다. `PYTHONPATH`에 저장소의 `src` 폴더를 넣고 `python -m awkit`으로 부르면 됩니다.

## 키트 넣기

```powershell
awkit kit init C:\work\my-project
```

지정한 폴더 아래에 `agent-work-kit`을 만들고 지침과 양식을 복사합니다. 폴더를 생략하면 현재 폴더에 만듭니다. 같은 이름의 폴더가 있으면 파일을 하나도 바꾸지 않고 종료 코드 `2`로 멈추는데, 그 안에 이미 작성한 적용표와 작업 기록이 있을 수 있기 때문입니다. 새 버전의 키트와 비교하고 싶다면 `--name agent-work-kit-new`처럼 다른 이름으로 설치하세요.

## 역할 파일 만들기

[위임 지침](../kit/delegation.md)의 다섯 역할을 공급자별 역할 파일로 만듭니다.

```powershell
awkit kit roles C:\work\my-project --provider claude
awkit kit roles C:\work\my-project --provider codex --model efficient=<모델>:medium --model standard=<모델>:medium --model judge=<모델>:high
```

등급은 `efficient`, `standard`, `judge`, `top` 네 가지이고, `--model 등급=모델`로 지정합니다. Codex는 `등급=모델:추론수준`처럼 추론 수준도 붙일 수 있습니다.

| 공급자 | 만드는 파일 | 모델을 정하는 방식 |
|---|---|---|
| Claude Code | `.claude/agents/<역할>.md` | 지정하지 않은 등급은 효율 `haiku`, 기본 `sonnet`, 판정 `opus`. 읽기 전용 역할에는 `tools`를 제한합니다. 최상위 등급은 호출할 때 모델을 덮어써서 씁니다. |
| Codex | `.codex/agents/<역할>.toml` | 지정한 등급에만 `model`과 `model_reasoning_effort`를 넣습니다. 지정하지 않은 역할은 경고와 함께 기본값을 물려받습니다. `top`을 주면 `analyst_top`을 하나 더 만듭니다. |

같은 이름의 파일이 있으면 덮어쓰지 않고 건너뜁니다. 하나도 만들지 못하고 모두 건너뛰었다면 종료 코드 `2`로 끝납니다. 공급자마다 다른 점은 [역할 양식 안내](../kit/templates/roles/README.md)에 자세히 적었습니다.

## 실행 기록에서 사용량 모으기

자식 에이전트가 실제로 어떤 모델로 돌았고 토큰을 얼마나 썼는지 실행 기록에서 읽어 모읍니다. 기록 파일이나 폴더를 직접 지정합니다.

```powershell
awkit usage $HOME\.claude\projects\<프로젝트 폴더>
awkit usage $HOME\.codex\sessions\2026\10 --since 2026-10-01 --json
```

폴더를 주면 그 아래의 `.jsonl` 파일을 모두 읽습니다. 스레드마다 공급자, 실제 모델과 추론 수준, 호출 수, 새로 보낸 입력, cache 쓰기, cache 읽기, 출력 토큰을 보여 주고 마지막 줄에 합계를 붙입니다. `--since`는 그 날짜(UTC) 이후에 바뀐 파일만 읽고, `--json`은 같은 내용을 구조화해서 내보냅니다.

| 공급자 | 읽는 방식 |
|---|---|
| Claude Code | 응답 하나가 여러 줄로 기록되므로 메시지 ID로 한 번만 셉니다. 자식 에이전트의 기록은 `subagent <ID>` 스레드로 따로 묶습니다. |
| Codex | 파일 하나를 스레드 하나로 봅니다. `turn_context`에서 모델과 추론 수준을, 마지막 `token_count`의 누적값에서 토큰을 읽습니다. 호출 수는 턴 수입니다. |

실행 기록 형식은 공급자가 공개적으로 약속한 형식이 아니라서 버전에 따라 바뀔 수 있습니다. Claude Code 쪽은 실제 기록으로 확인했습니다. Codex 쪽은 실제 기록에서 확인된 필드 이름을 따랐지만 최신 파일로는 돌려 보지 않았으니, 처음 쓸 때 한두 스레드의 값을 Codex 화면의 사용량과 맞춰 보세요. 형식을 알아보지 못한 파일은 건너뛰고 그 개수를 알려 줍니다.

기록에는 대화 내용이 들어 있습니다. 이 명령은 모델과 토큰 필드만 읽고 내용은 출력하지 않지만, 결과를 공유할 때는 파일 경로에 프로젝트 이름이 드러나지 않는지 확인하세요.

## 검토 채널

두 세션이 같은 SQLite 파일에 메시지를 쌓으며 검토를 주고받습니다. 구현을 맡은 세션은 `main`, 검토하는 세션은 `reviewer`로 씁니다. 기본 파일은 현재 폴더의 `.awkit/channel.sqlite3`이고, 다른 파일을 쓰려면 양쪽 세션에 같은 `--db 경로`를 지정합니다.

한 터미널에서 두 역할을 번갈아 실행해 보면 흐름을 금방 볼 수 있습니다.

```powershell
$db = Join-Path (Get-Location) '.awkit/example-review.sqlite3'
awkit channel --db $db post main reviewer review --snap aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa --body "권한 검사 변경을 검토해 주세요."
awkit channel --db $db wait reviewer request --max 0
awkit channel --db $db post reviewer main re --reply-to M-001 --body "확인한 버전에서 중요한 결함은 찾지 못했습니다."
awkit channel --db $db wait main reply M-001 --max 0
awkit channel --db $db export
awkit channel --db $db post main reviewer close --body "검토 결과를 반영했습니다."
```

새 파일에서는 첫 요청이 `M-001`, 첫 응답이 `R-001`이 됩니다. 기록이 쌓인 파일이라면 `post`가 출력한 ID를 `--reply-to`와 `wait … reply`에 넣으세요. 채널을 닫은 파일에는 더 쓸 수 없으니 다음 검토는 새 파일로 시작합니다.

`--snap`에는 검토할 버전의 식별자를 7~64자리 소문자 16진수로 넣습니다. 예제의 `aaaa…`는 모의 값입니다. 작업 중인 변경을 고정한 식별자는 [`review snapshot`](tools.md#검토할-변경본을-고정하기)으로 만들 수 있습니다.

### 본문 전달

| 방법 | 쓰는 경우 |
|---|---|
| `--body "본문"` | 한 줄짜리 짧은 메시지 |
| `--body-file 경로` | 여러 줄 본문이나 에이전트가 파일로 써 둔 의견. UTF-8로 읽습니다. |
| 표준 입력 | 다른 명령의 출력을 그대로 넘길 때. PowerShell에서는 먼저 `$OutputEncoding = [System.Text.UTF8Encoding]::new()`를 실행해야 한글이 깨지지 않습니다. |

빈 본문은 받지 않습니다.

### 메시지 종류와 대기

요청에는 `review`, `scout`, `test`, `draft`, `question`, `final` 가운데 하나를 씁니다. 알림은 `notice`, 응답은 `re`, 반박은 `rebut`입니다. `re`와 `rebut`에는 `--reply-to`가 필요하고, 상대 역할이 실제로 보낸 메시지만 가리킬 수 있습니다. 채널을 닫는 `close`는 `main`만 보냅니다.

| 명령 | 돌려주는 내용 | 읽은 뒤 |
|---|---|---|
| `wait … request` | 아직 답하지 않은 요청과 반박 | 응답할 때까지 계속 대기 목록에 남습니다. |
| `wait … new` | 해당 역할에 새로 도착한 메시지 | 읽은 위치가 앞으로 옮겨집니다. 같은 역할로 읽는 세션들은 이 위치를 공유합니다. |
| `wait … reply ID` | 그 메시지에 붙은 응답과 반박 | 기록은 그대로입니다. |
| `export` | 채널 전체의 Markdown | 읽은 위치를 바꾸지 않습니다. |

기본으로 최대 120초를 기다리고, `--max 0`이면 한 번만 확인합니다. `--json`을 붙이면 구조화된 결과가 나옵니다. 기다리는 동안에는 읽기 잠금만 잡으므로 여러 세션이 함께 기다려도 메시지 기록을 막지 않습니다.

| 종료 코드 | 뜻 |
|---|---|
| `0` | 메시지를 찾았습니다. |
| `1` | 시간이 다 지났습니다. |
| `2` | 명령을 잘못 썼거나 저장소 오류가 났습니다. |
| `3` | `reviewer`가 `main`의 종료 통보를 받았습니다. |

이 채널은 메시지를 저장하고 읽어 줄 뿐입니다. 에이전트를 실행하거나 대화를 외부 서비스로 보내지 않습니다.

### 파일을 둘 위치

같은 PC에서 신뢰하는 세션들이 함께 쓰는 로컬 디스크에 두세요. 실행 중인 SQLite 파일을 Dropbox, OneDrive나 네트워크 공유로 동기화하면 기록이 깨질 수 있어 지원하지 않습니다. 인증 기능은 따로 없고, 파일에 접근할 수 있는 사람은 누구나 읽고 쓸 수 있습니다.

시간은 UTC로 기록합니다. Markdown으로 내보낼 때 본문을 인용문으로 감싸기 때문에, 본문에 메시지 제목처럼 생긴 줄을 넣어도 다른 메시지로 보이지 않습니다.

## 배포 실행기

### 모의 배포로 익히기

예제는 서버에 접속하지 않고 `examples/local-release/.demo-target/` 안의 JSON 파일만 바꿉니다. 저장소 폴더에서 실행 기록이 없는 상태로 시작하세요.

```powershell
$config = 'examples/local-release/pipeline.toml'
awkit pipeline --config $config plan
awkit pipeline --config $config deploy aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
awkit pipeline --config $config deploy bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb
awkit pipeline --config $config status
awkit pipeline --config $config history
```

`plan`은 실행할 단계만 보여 주고 프로젝트 명령은 부르지 않습니다. 상태 파일도 만들지 않습니다. `status`에는 두 번째 버전의 전체 식별자와 `service: 통과`가 나와야 하고, `history`는 검사를 통과한 버전을 최근 것부터 보여 줍니다.

모의 예제는 `f`로 시작하는 식별자를 불량 버전으로 취급합니다. 하나 배포해 보세요.

```powershell
awkit pipeline --config $config deploy ffffffffffffffffffffffffffffffffffffffff --json
$LASTEXITCODE
awkit pipeline --config $config status
```

결과는 `failed-restored`, 종료 코드는 `1`입니다. 상태를 다시 보면 직전 정상 버전인 `bbbb…`가 돌고 있습니다. 앱은 되돌렸어도 요청한 배포가 실패했다는 사실은 기록에 남습니다. 예제는 데이터를 바꾸지 않아 이전 앱으로 안전하게 돌아갈 수 있기 때문에 자동 복귀를 켜 두었습니다.

`rollback`은 버전 인자 없이 실행하며, 이력에서 현재 버전 바로 앞의 정상 버전으로 돌아갑니다. 거듭 실행하면 한 단계씩 더 뒤로 가고, 더 돌아갈 버전이 없으면 대상을 건드리지 않은 채 실패로 기록합니다. 이미 실행 중인 버전을 다시 배포하면 상태만 확인하고 `outcome: already-current`로 기록하며 배포 명령은 부르지 않습니다.

### 프로젝트에 연결하기

[예제 설정](../examples/local-release/pipeline.toml)을 프로젝트로 복사해 그 프로젝트의 배포 도구에 맞게 고칩니다. 설정 파일이 실행할 프로그램을 정하므로 신뢰할 수 있는 사람이 관리하는 파일이어야 합니다.

설정 맨 위에는 `schema_version = 1`을 둡니다. `[pipeline]`에는 다음 값을 넣습니다.

| 키 | 뜻 |
|---|---|
| `target` | 배포 대상의 이름. 영문, 숫자, 점, 밑줄, 하이픈만 씁니다. |
| `state_dir` | 실행 기록과 잠금을 둘 폴더. 기본값은 `.awkit/releases`입니다. |
| `timeout_seconds` | 명령 하나에 허용하는 시간. 기본값은 120초입니다. |
| `required_checks` | 검증 결과에 반드시 있어야 하는 검사 이름 목록 |
| `auto_rollback` | 배포가 실패했을 때 직전 버전으로 자동 복귀할지 여부. 기본값은 `false`입니다. |

상대경로는 설정 파일이 있는 폴더를 기준으로 해석합니다.

`[commands]`에는 아래 다섯 명령을 인자 배열로 적습니다. 실행기는 배열을 셸 문자열로 합치지 않고 그대로 프로그램에 넘깁니다. Python 스크립트가 아니어도 되지만, 출력 형식과 종료 코드 약속은 어떤 언어로 짜든 지켜야 합니다.

| 명령 | 프로젝트에서 구현할 일 |
|---|---|
| `preflight` | 대상을 바꾸지 않고 대상 이름과 현재 버전을 JSON으로 출력합니다. |
| `backup` | 복구에 필요한 데이터를 보존합니다. 실패하면 0이 아닌 코드로 끝냅니다. 첫 배포에서도 실행되며, 보존할 데이터가 없다면 그 이유를 적어 두고 아무것도 하지 않는 명령을 연결합니다. |
| `deploy` | 요청받은 버전을 적용합니다. 전송, 빌드, migration처럼 필요한 일을 모두 마친 뒤 끝냅니다. |
| `verify` | 실제로 실행 중인 버전과 검사 결과를 JSON으로 출력하고 `0`으로 끝냅니다. 검사가 실패하더라도 보고서를 낼 수 있다면 `ok: false`로 알려야 합니다. |
| `rollback` | `{release}`로 받은 버전으로 앱을 되돌리고 끝냅니다. DB 복원은 실행기가 하지 않습니다. |

배포 명령은 작업을 백그라운드로 떼어 내지 말고 끝날 때까지 기다려야 합니다. 실행기는 명령이 끝난 시점을 작업이 끝난 시점으로 봅니다.

인자에는 아래 자리표시자를 쓸 수 있습니다. 값에 공백이 있어도 배열의 한 원소로 들어가고, 넘길 버전이 없으면 빈 문자열이 됩니다.

| 표기 | 들어가는 값 |
|---|---|
| `{python}` | 실행기가 쓰는 Python 경로 |
| `{project}` | 설정 파일이 있는 폴더 |
| `{target}` | 배포 대상 이름 |
| `{release}` | 그 단계에서 적용하거나 확인할 버전 |
| `{previous}` | 그 단계에 함께 넘기는 이전 버전 |
| `{run_dir}` | 이번 실행의 기록 폴더. 실행 폴더를 만들지 않는 `status`에서는 `state_dir` |

### 출력 형식

`preflight`는 아래 형태로 출력합니다. 아직 배포한 적이 없으면 `release`를 `null`로 둡니다.

```json
{"target": "local-demo", "release": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
```

`verify`는 실제로 실행 중인 버전을 읽어서 출력해야 합니다. 요청받은 버전 문자열을 그대로 되돌려 주면 검증이 의미를 잃습니다.

```json
{
  "target": "local-demo",
  "release": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "checks": [{"name": "service", "ok": true}]
}
```

`required_checks`의 이름이 모두 들어 있어야 하고 `ok`는 불리언이어야 합니다. 검사 목록이 비었거나, 이름이 겹치거나, 대상이 다르거나, JSON 형식이 맞지 않으면 상태를 알 수 없는 출력으로 보고 거부합니다. 배포 뒤 검증에서는 실제 버전이 요청한 버전과 다를 때도 실패입니다. 명령 자체가 0이 아닌 코드로 끝나면 출력 내용과 상관없이 실패로 처리합니다.

릴리스 식별자는 7~64자리 소문자 16진수입니다. 실제로 쓸 때는 충돌하지 않도록 전체 Git commit이나 아티팩트 해시를 넣으세요. 식별자가 실제 코드와 맞는지는 프로젝트의 명령이 Git 객체나 배포 manifest와 대조해서 확인해야 합니다. 실행기는 넘겨받은 문자열만 보고 동일성을 보장하지 못합니다.

### `status`와 `history`

`status`는 현재 버전과 검사별 결과를 보여 줍니다. 모두 통과하면 `0`, 하나라도 실패하면 `1`로 끝납니다. 확인 명령이 `1`~`125` 사이의 코드로 실패하면 그 코드를 그대로 돌려주고, 그 밖의 코드는 `1`로 바꿉니다. `history`는 `rollback`이 따라갈 정상 버전 목록입니다. 두 명령 모두 `--json`을 지원합니다.

## 실패와 복귀

실행기는 대상 확인, 현재 버전 검사, 백업, 배포, 배포 후 검사 순서로 움직이고, 명령마다 `timeout_seconds`를 적용합니다. `deploy`와 `rollback`이 끝나면 결과는 아래 여섯 가지 중 하나입니다.

| 결과 | 뜻 |
|---|---|
| `passed` | 요청한 버전이 실행 중이고, 검증 명령이 돌려준 검사가 모두 통과했습니다. |
| `failed` | 대상을 바꾸기 전에 실패했습니다. 대상은 그대로입니다. |
| `failed-restored` | 배포는 실패했지만 직전 버전으로 돌아가 검사를 통과했습니다. |
| `failed-unrecovered` | 대상을 바꾸다 실패했고 복구를 확인하지 못했습니다. |
| `rollback-failed` | 자동 복귀 명령이나 복귀 뒤 검사가 실패했습니다. |
| `uncertain` | 시간 초과나 중단으로 최종 상태를 알 수 없습니다. |

자동 복귀는 `auto_rollback = true`이고 배포 전 버전이 검사를 통과한 상태였을 때만 시도합니다. 바뀐 데이터를 이전 앱이 읽을 수 있다는 근거가 있을 때만 켜세요. DB 이미지 업그레이드나 되돌릴 수 없는 migration, 데이터 복원은 프로젝트에서 따로 설계하고 검증해야 합니다.

### 현재 버전이 이미 고장 났을 때

현재 버전의 검사가 실패하면 `deploy`는 대상을 바꾸지 않고 `verify-current` 단계에서 `failed`로 멈춥니다. 고장 난 줄 모르고 그 위에 배포하는 일을 막으려는 것입니다. 고친 버전을 올리려면 의도를 밝히세요.

```powershell
awkit pipeline --config $config deploy cccccccccccccccccccccccccccccccccccccccc --allow-unhealthy-current
```

옵션을 붙여도 백업과 배포, 배포 후 검사는 똑같이 거칩니다. 시작할 때의 검사 결과는 기록의 `current_health`에 남습니다. 이미 고장 난 버전으로 돌아가 봐야 복구가 아니므로 이때는 자동 복귀를 하지 않습니다. 같은 버전을 다시 올리면 이번에는 배포 명령을 실제로 실행하고 `outcome: redeployed`로 기록합니다.

`rollback`에는 이 옵션이 필요 없습니다. 현재 버전이 고장 났더라도 이력에 있는 정상 버전으로 돌아갑니다.

### 상태를 알 수 없을 때

마지막 기록이 `running`, `uncertain`, `rollback-failed`, `failed-unrecovered` 중 하나면 다음 배포와 `rollback`을 모두 막습니다. 실제 대상을 직접 확인하고 필요한 복구를 마친 다음 `reconcile`을 실행하세요.

```powershell
awkit pipeline --config $config reconcile
```

`reconcile`은 잠금을 잡고 현재 버전과 검사 결과를 다시 읽어 기록합니다. 모두 통과하면 `reconciled`, 실패한 검사가 있으면 `reconciled-unhealthy`로 남기고 종료 코드 `1`을 돌려줍니다. 어느 쪽이든 차단은 풀립니다. `reconciled-unhealthy` 다음에는 고친 버전을 `--allow-unhealthy-current`로 배포하거나 `rollback`으로 정상 버전에 돌아가면 됩니다. `reconcile`은 배포도 데이터 복원도 하지 않으며, 현재 버전이 없는 대상에는 쓸 수 없습니다. 실패 기록을 지우는 것으로 이 과정을 건너뛰지 마세요.

### 시간 초과

명령은 따로 만든 프로세스 그룹에서 실행합니다. 제한 시간을 넘기면 그 명령이 띄운 ssh나 docker 같은 하위 프로세스까지 한꺼번에 종료합니다. Windows에서는 `taskkill /T`, Linux에서는 프로세스 그룹 종료를 씁니다.

원격 서버에서 이미 시작된 작업은 멈추지 못합니다. 그래서 대상을 바꾸는 도중 시간이 초과되면 자동 복귀를 시도하지 않고 `uncertain`으로 기록합니다. 복구에 들어가기 전에 원격 작업이 정말 끝났는지 확인하세요.

### 실행 기록

| 위치 | 내용 |
|---|---|
| `state_dir/last-run.json` | 마지막 실행의 결과 |
| `state_dir/history.json` | 검사를 통과한 버전 목록. `rollback`이 이 목록을 따라갑니다. |
| `state_dir/runs/<run_id>/result.json` | 실행별 단계, 걸린 시간, 종료 코드, 검증 결과 |
| `state_dir/runs/<run_id>/logs/` | 단계별 표준 출력과 오류 원문 |

`reconcile`도 실행 폴더를 하나 만들어 같은 형식으로 남깁니다. 0.1.0에서 만든 상태 폴더처럼 이력 파일이 없으면 마지막 성공 기록에서 이력을 되살립니다.

출력 원문이 기록에 그대로 저장되므로 비밀값을 명령 인자나 검사 이름, 출력에 넣지 마세요. 프로젝트 명령은 실행기를 부른 프로세스의 환경변수를 그대로 물려받습니다.

### 잠금

같은 `state_dir`을 쓰는 실행기끼리는 SQLite 잠금으로 동시 배포를 막고, 프로세스가 끝나면 잠금도 풀립니다. 그러니 같은 대상을 다루는 설정은 반드시 같은 `state_dir`을 가리켜야 합니다.

대상 서버를 잠그는 기능은 없습니다. 여러 PC에서 같은 서버에 배포한다면 배포 시작부터 복귀가 끝날 때까지 유지되는 서버 쪽 잠금을 프로젝트에서 마련해야 합니다. Docker 이미지 전송, 인증서, 계정, SSH도 실행기가 설정해 주지 않습니다.

처음 실제 대상에 연결할 때는 새 환경에서 버전 대조, 백업 복원, 원격 잠금, 이전 앱과 데이터의 호환성을 직접 확인하세요. 모의 예제는 파일만 바꾸므로 이런 확인을 대신하지 못합니다.

## 검사와 빌드

저장소 폴더에서 아래처럼 검사를 돌립니다. 표준 라이브러리 `unittest`를 쓰며 네트워크나 실제 서버가 필요 없습니다. 변경본 검사 테스트에는 Git이 있어야 합니다.

```powershell
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
python -m unittest discover -s tests -v
```

화면 캡처 검사는 기본으로 건너뜁니다. Playwright와 브라우저를 갖춘 뒤 `AWKIT_UI_TEST=1`을 지정하면 함께 실행하고, Edge로 돌리려면 `AWKIT_BROWSER_CHANNEL=msedge`도 지정합니다.

릴리스 파일은 `scripts/build_release.py`가 만듭니다. 같은 Python 환경에 `setuptools>=68`과 `wheel`이 있어야 하고, 결과로 wheel과 키트 ZIP, `SHA256SUMS`가 `dist/`에 생깁니다.

```powershell
python -m pip install "setuptools>=68" wheel
python scripts/build_release.py
```

패키지 버전과 같은 태그(예: `v0.2.0`)를 올리면 GitHub Actions가 검사를 다시 돌린 뒤 같은 파일로 릴리스를 만듭니다. 검사 환경별 결과는 [검증 범위](validation.md)에 있습니다.
