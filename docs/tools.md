# 추가 도구

검토할 변경을 고정하는 `review snapshot`, 고정한 버전을 따로 검사하는 `review check`, 보존한 결과물을 대조하는 `review verify`, 채택본을 남기고 비교하는 `review accept`와 `review compare`, 정적 문서를 발행하는 `publish`, 화면을 여러 폭으로 캡처하는 `ui`를 다룹니다. 설치 방법은 [CLI 사용법](cli.md#설치)에 있습니다. 빌드와 검사는 모두 프로젝트에 이미 있는 명령을 연결해서 쓰므로 개발 언어는 상관없습니다.

각 기능의 개발 범위는 [역할과 범위](scope.md)를 따릅니다. 아래 명령과 설정은 현재 구현을 설명합니다.

## 검토할 변경본을 고정하기

검토에 넣을 파일을 저장소 최상위 기준의 경로로 지정합니다.

```powershell
$snap = awkit review --repo . snapshot src/example.js docs/guide.md
```

명령은 Git commit의 전체 식별자 하나를 출력합니다. 현재 HEAD에 지정한 파일의 작업 내용만 얹은 commit입니다. 다른 파일에 있던 커밋하지 않은 변경은 들어가지 않고, 실제 HEAD와 스테이징 상태, 작업 파일도 손대지 않습니다. 새로 만든 파일이나 지운 파일도 이름을 지정하면 반영됩니다. 디렉터리를 통째로 지정하거나 Git이 무시하는 파일을 넣으면 거부합니다.

HEAD에 이미 커밋된 파일은 모두 스냅샷에 그대로 들어갑니다. 비밀정보를 찾아서 빼 주는 기능은 없습니다. 스냅샷은 어느 브랜치에도 연결되지 않은 로컬 객체라 `git gc` 같은 정리 작업에서 사라질 수 있습니다. 가까운 시점의 검토에만 쓰고, 오래 남길 근거는 프로젝트의 변경 이력에 연결하세요.

## 별도 작업 폴더에서 검사하기

```powershell
awkit review --repo . check $snap --config examples/review/checks.toml
```

`$snap` 자리에는 앞에서 받은 스냅샷이나 검사할 commit의 전체 식별자를 넣습니다. 실행기는 그 버전으로 Git worktree를 새로 만들고, 준비 명령을 실행한 다음 검사 명령을 실행합니다. 지금 작업 중인 폴더의 상태는 결과에 섞이지 않습니다.

설정 파일은 스냅샷 밖에서 읽고, 그 SHA-256을 결과에 함께 남깁니다. 실행할 명령이 들어 있는 파일이니 신뢰하는 사람이 관리해야 합니다. [검사 예제](../examples/review/checks.toml)를 복사해 준비 단계와 검사를 프로젝트 명령으로 바꾸세요.

| 설정 | 뜻 |
|---|---|
| `schema = 1` | 설정 형식 |
| `timeout_seconds` | 명령 하나에 허용하는 시간. 기본값은 300초입니다. |
| `[[setup]]` | 준비 명령. 하나라도 실패하면 검사 명령은 실행하지 않습니다. |
| `[[checks]]` | 검사 명령. 하나가 실패해도 나머지를 계속 실행합니다. |
| `[env]` | 명령에 넘길 환경변수. 실행기를 부른 환경도 그대로 물려받습니다. |
| `artifacts`, `required_artifacts` | 검사 뒤 실행 기록 폴더에 보존할 파일 패턴. 아래 [결과물 보존](#검사한-결과물-보존하기)을 보세요. |

단계마다 서로 다른 `name`과 `argv`를 줍니다. `cwd`는 해당 단계의 실행 폴더이며 생략하면 worktree 루트에서 실행합니다. `argv`는 실행 파일과 인자를 나눈 배열이고 셸을 거치지 않습니다. Node.js라면 `["node", "--test"]`, Go라면 `["go", "test", "./..."]`처럼 쓰면 됩니다. 이 두 줄은 형식을 보여 주는 예시이고, 해당 언어 프로젝트에서 실제로 돌려 본 결과는 아닙니다.

`cwd`에는 `packages/sdk`처럼 worktree 루트 기준 상대경로를 `/`로 구분해 적습니다. 루트는 `.`으로 표시합니다. 절대경로, `..`, `.git`과 빈 경로는 설정 오류로 거부합니다. 앞선 준비 단계가 만든 폴더도 사용할 수 있습니다. 실행 직전에 폴더가 있는지, 연결 경로가 worktree 밖으로 나가는지 확인합니다. 이 확인에 실패하면 해당 단계가 실패하며, 준비 단계 실패 때는 검사를 시작하지 않습니다. 검사 단계 실패 때는 나머지 검사를 계속합니다. 결과 JSON의 각 단계에는 실제 실행 폴더를 `cwd`로 남깁니다.

```toml
[[checks]]
name = "sdk-tests"
cwd = "packages/sdk"
argv = ["python", "-m", "pytest", "-q"]
```

이 예시는 프로젝트 환경의 `python`을 PATH에서 찾습니다. `{python}`은 **awkit을 실행하는 인터프리터**이므로 대상 프로젝트의 런타임과 구분하세요. 가상환경을 공유한다면 해당 환경이 원래 작업 폴더 대신 검사할 worktree의 코드를 읽도록 설정해야 합니다.

인자와 환경변수 값에는 `{python}`, `{worktree}`, `{run_dir}`, `{run_id}`를 쓸 수 있습니다. 명령에는 `AWKIT_WORKTREE`, `AWKIT_RUN_DIR`, `AWKIT_RUN_ID` 환경변수도 들어갑니다. worktree를 나눠도 DB, 포트, Unix 소켓과 장치는 공유될 수 있습니다. 실행 ID로 필요한 자원을 할당하고 준비 완료, 시나리오 완료와 정리 조건을 프로젝트 명령에 넣으세요. 계속 대기하는 프로그램은 시나리오 결과를 확인하고 프로세스를 정리하는 실행 명령으로 감싸야 합니다.

결과 JSON의 `run_dir`에 `result.json`과 단계별 로그가 남습니다. 정상적으로 끝나면 실행기가 만든 worktree만 정리하고, `--keep`을 붙이면 남겨 둡니다. 기록 폴더의 위치는 `--runs-root`로 바꿀 수 있습니다.

| 종료 코드 | 뜻 |
|---|---|
| `0` | 모든 준비 명령과 검사 명령이 통과했습니다. |
| `1` | 실패한 명령이 있거나, 시간 초과로 결과를 확정하지 못했습니다. |
| `2` | 설정 파일이나 Git 작업에 문제가 있어 실행하지 못했습니다. |

시간이 초과되거나 중단되면 검사 명령과 그 명령이 띄운 하위 프로세스를 함께 종료하고, 결과를 `uncertain`으로 남깁니다. 이때 worktree는 지우지 않고 남겨 둡니다. 원격 서버나 다른 서비스에서 시작된 작업까지 멈추지는 못하니, 확인한 뒤 Git의 worktree 제거 절차로 정리하세요.

이 실행기는 신뢰하지 않는 프로그램을 가두는 샌드박스가 아닙니다. 로그에는 실행한 프로그램의 출력이 그대로 들어가므로 자동으로 공개되는 곳에 두지 마세요.

## 검사한 결과물 보존하기

검사 설정에 `artifacts`를 적으면 실행기가 모든 단계를 마친 뒤 worktree에서 해당 파일을 실행 기록 폴더의 `artifacts/`로 복사하고 크기와 SHA-256을 기록합니다. `required_artifacts`에 적은 패턴에 맞는 파일이 하나도 없으면, 검사 명령이 모두 통과했어도 결과는 `failed`입니다. 명령이 `0`으로 끝났지만 약속한 파일을 만들지 않은 경우를 잡기 위한 것입니다.

```toml
schema = 1
artifacts = ["dist/*.whl", "reports/**/*.html"]
required_artifacts = ["dist/*.whl"]
```

패턴은 worktree 루트 기준의 상대경로이며 `*`, `?`, `**`를 쓸 수 있습니다. 절대경로, `..`, `.git` 아래 경로는 설정 오류로 거부합니다. 연결 파일과 worktree 밖을 가리키는 파일은 복사하지 않고 `skipped_artifacts`에 적습니다. 검사가 실패한 실행에서도 패턴에 맞는 파일은 보존하므로, 실패 진단 파일을 같은 방식으로 남길 수 있습니다.

실행 기록 폴더에는 다음이 남습니다.

| 파일 | 내용 |
|---|---|
| `result.json` | 검사한 commit, 설정 해시, 단계별 결과, 보존한 파일의 크기와 해시, 빠진 필수 결과물 |
| `config.toml` | 실행에 사용한 검사 설정 원본 |
| `NN.log` | 단계별 출력 |
| `artifacts/` | 보존한 파일과 `manifest.json` |

`manifest.json`은 검사한 commit, 설정 해시, 실행 ID와 파일별 크기·해시를 담습니다. 나중에 보존한 파일이 그대로인지 확인하려면 실행 기록 폴더를 `verify`에 넘깁니다.

```powershell
awkit review verify .awkit/reviews/review-abc123
```

`verify`는 manifest의 각 파일을 다시 읽어 `ok`, `changed`, `missing`으로 보고하고, manifest에 없는 파일은 `unexpected`에 적습니다. `result.json`이 아직 `running`이면 중단된 실행으로 보고 `interrupted`를 `true`로 표시합니다. 모든 파일이 `ok`이고 중단이나 추가 파일이 없을 때만 `verified`가 `true`이고 종료 코드가 `0`입니다. 해시 일치는 파일이 검사 당시와 같은 바이트라는 뜻이며, 내용이 옳은지는 검토 기록이 말해 줍니다.

## 채택본을 남기고 비교하기

검사 결과를 보고 "이 버전이 맞다"고 판단했다면 그 실행을 채택본으로 남깁니다. 이후 수정본이 채택본에서 무엇이 달라졌는지 보는 데 씁니다. 좋다고 한 문서나 디자인이 다음 수정에서 퇴보하는 일을 잡기 위한 것입니다.

```powershell
awkit review accept .awkit/reviews/review-abc123
awkit review accept .awkit/reviews/review-abc123 --label v1
```

`accept`는 먼저 `verify`와 같은 대조를 거쳐 보존한 파일이 manifest와 일치하는지 확인하고, 실행 기록 폴더의 `artifacts/`를 저장소의 `.awkit/accepted/<label>/`로 복사합니다. 기본 label은 `accepted`이고, 같은 label로 다시 채택하면 이전 채택본을 바꿉니다. 채택본 폴더의 `accepted.json`에 어느 실행, 어느 commit, 어느 설정에서 나온 파일인지와 파일별 해시가 남습니다. 보존한 파일이 없는 실행은 채택할 수 없습니다.

```powershell
awkit review compare                                   # 작업 폴더의 파일을 채택본과 비교
awkit review compare --run .awkit/reviews/review-def456 --diff   # 새 실행의 결과물을 채택본과 비교
```

`compare`는 채택본의 파일마다 `same`, `changed`, `missing`을 보고합니다. `--run`을 주면 그 실행 기록 폴더의 `artifacts/`를, 주지 않으면 작업 폴더의 같은 경로를 비교합니다. `--diff`를 붙이면 바뀐 텍스트 파일의 unified diff를 함께 냅니다. 모두 `same`일 때만 종료 코드 `0`입니다. 바뀐 것이 의도한 수정뿐인지는 사람이 diff를 보고 판단합니다.

[하위 폴더 검사 예제](../examples/review/subdirectory.toml)는 `examples/review`에서 설정 파일을 검사하고 그 파일을 보존합니다. 이 저장소의 예제 파일이 들어 있는 commit을 대상으로 실행하세요.

```powershell
awkit review check $snap --config examples/review/subdirectory.toml --runs-root .awkit/reviews
```

기본 기록 위치는 운영체제의 임시 폴더입니다. 오래 보존할 결과는 `--runs-root`로 보관 위치를 지정하세요. 기록에는 소스와 로그가 포함될 수 있으므로 공개할 파일은 따로 정합니다.

## 정적 문서 발행하기

프로젝트의 문서 생성기로 HTML을 만든 다음, 그 결과물을 발행합니다. 아래 예제는 미리 만들어 둔 모의 HTML을 씁니다.

```powershell
awkit publish --output .awkit/site --project sample build --source examples/site --files examples/site-files.json
```

[허용 파일 목록](../examples/site-files.json)은 원본 폴더 기준의 상대경로를 담은 JSON 배열입니다. `index.html`이 반드시 있어야 하고, 목록에 적은 파일만 복사합니다. 처음 발행할 때는 빈 폴더를 출력 위치로 지정하세요. 다른 파일이 들어 있는 폴더는 덮어쓰지 않습니다.

발행 전에 HTML 링크와 문서 안의 앵커, CSS의 단순한 `url()` 참조가 모두 허용 목록 안의 파일을 가리키는지 확인합니다. 자원은 상대경로로 연결해야 합니다. 외부 웹페이지로 가는 링크는 괜찮지만, 외부에서 불러오는 이미지나 스타일 같은 자원은 거부합니다. CSS `@import`, `srcset`, `srcdoc`, `base`는 아직 지원하지 않습니다.

JavaScript가 실행 중에 만드는 주소나 내용의 정확성, 접근성, HTML의 안전성은 검사하지 않습니다. 직접 빌드해 신뢰할 수 있는 결과물만 넣으세요.

발행 버전은 파일 내용의 해시로 정합니다. 새 버전 폴더에 복사해 다시 검사한 뒤에야 진입점인 `index.html`을 원자적으로 바꿉니다. 검사나 교체가 실패하면 이전 진입점이 그대로 남습니다. 같은 입력을 다시 발행하면 같은 버전을 다시 씁니다.

이전 버전으로 돌아갈 때는 발행 결과의 `version`에 나온 전체 해시를 `$version` 자리에 넣습니다.

```powershell
awkit publish --output .awkit/site --project sample restore $version
```

복원할 때도 프로젝트 이름과 파일 해시, 링크를 다시 확인합니다. 버전 폴더의 파일이 바뀌었거나 목록에 없는 파일이 끼어 있으면 거부합니다. 지난 버전들은 지우지 않고 디스크에 남겨 둡니다.

같은 출력 폴더를 쓰는 발행기끼리는 SQLite 잠금으로 동시에 바꾸지 못하게 막습니다. 다만 여러 PC나 클라우드 동기화 폴더에서는 이 잠금이 통하지 않습니다. 브랜치별 대기열이나 오래된 요청을 거르는 기능도 없어서, 부른 순서대로 발행됩니다. 순서는 부르는 쪽에서 관리하고, 외부 업로드와 호스팅은 프로젝트의 배포 절차에 연결하세요.

## 여러 폭의 화면을 모아 보기

화면 캡처에만 Playwright와 브라우저가 추가로 필요합니다.

```powershell
python -m pip install ".\agent_work_kit-0.2.0-py3-none-any.whl[ui]"
python -m playwright install chromium
```

이미 설치된 Edge를 쓰려면 Chromium을 설치하지 말고 캡처 명령에 `--channel msedge`를 붙이세요. 브라우저별 설치 조건은 [Playwright 안내](https://playwright.dev/python/docs/browsers)에 있습니다.

모의 페이지로 시험하려면 한 터미널에서 미리보기 서버를 띄우고, 다른 터미널에서 캡처합니다.

```powershell
python -m http.server 8765 --bind 127.0.0.1 --directory examples/site
awkit ui --config examples/ui/pages.json --output .awkit/screens
```

실제 프로젝트에서는 [설정](../examples/ui/pages.json)의 주소와 화면 경로를 검토용 미리보기 서버에 맞게 바꿉니다.

| 설정 | 뜻 |
|---|---|
| `base_url` | 캡처할 서버의 원점. 인증값 없는 HTTP나 HTTPS 주소여야 합니다. |
| `pages` | 캡처할 화면 1~20개. 각각 `name`과 `/`로 시작하는 `path`를 줍니다. |
| `widths` | 캡처할 폭 1~6개. 240~3840 사이의 서로 다른 값이며 기본값은 `[320, 1440]`입니다. |
| `timeout_ms` | 화면 하나를 기다리는 시간. 기본값은 15000입니다. |

결과 폴더는 비어 있어야 합니다. 화면마다 지정한 폭으로 전체 PNG를 저장하고, `index.html`에 모아 보여 줍니다. 한 장으로 받아 보려면 `sheet.png`를 여세요. `result.json`에는 가로 넘침과 화면 밖으로 나간 조작 요소, 캡처 실패가 기록되고, 이런 문제가 하나라도 있으면 종료 코드 `1`을 돌려줍니다.

캡처 도구는 지정한 경로만 엽니다. 링크를 따라가거나 버튼을 누르거나 로그인하지 않습니다. 새 브라우저 환경에서 같은 원점의 GET과 HEAD 요청만 허용하고, 외부 자원과 그 밖의 HTTP 메서드, 서비스 워커, WebSocket은 막습니다. 이 제한은 보안 장치가 아닙니다. GET 요청만으로도 서버 상태가 바뀔 수 있으니 검토용 미리보기 화면에만 쓰세요.

자동 검사가 찾는 문제는 위 두 가지뿐입니다. 접근성이나 업무 흐름, 디자인의 완성도는 사람이 캡처를 보고 판단해야 합니다.
