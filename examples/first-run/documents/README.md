# 문서 예제

작은 한국어 문서 묶음으로 검사 실패를 확인하고, 고친 뒤 다시 검사하고, 검사한 문서를 보존하는 과정을 끝까지 해 봅니다. `docs/` 아래의 문서 세 개와 링크·제목을 검사하는 `check_docs.py`, 검사 설정 `checks.toml`, 이 예제의 [프로젝트 적용표](project.md)가 들어 있습니다. 문서 하나에는 일부러 깨진 링크가 있습니다.

Python 3.11 이상, Git, `awkit`이 필요합니다. 아래 명령은 이 폴더에서 실행합니다.

## 1. Git 저장소로 만들기

검사는 Git commit을 대상으로 실행하므로 먼저 현재 상태를 commit합니다.

```sh
git init
git add -A
git commit -m "Start the documents example"
```

## 2. 실패를 확인하기

현재 commit을 별도 worktree에 꺼내 검사합니다. 실행 기록은 `.awkit/reviews/` 아래에 남습니다.

```sh
awkit review check "$(git rev-parse HEAD)" --config checks.toml --runs-root .awkit/reviews
```

PowerShell에서는 `awkit review check (git rev-parse HEAD) --config checks.toml --runs-root .awkit/reviews`로 실행합니다.

결과 JSON의 `status`는 `failed`입니다. `run_dir`에 적힌 폴더의 `01.log`를 열면 어느 문서의 어느 링크가 깨졌는지 나옵니다.

## 3. 고치고 다시 검사하기

`docs/index.md`에서 로그가 가리킨 링크를 실제로 있는 파일로 고칩니다. 그런 다음 고친 파일만 담은 스냅샷을 만들어 검사합니다. 작업 중인 파일과 commit 상태는 그대로 남습니다.

```sh
snap=$(awkit review snapshot docs/index.md)
awkit review check "$snap" --config checks.toml --runs-root .awkit/reviews
```

PowerShell에서는 `$snap = awkit review snapshot docs/index.md`로 받습니다.

이번에는 `status`가 `passed`이고, `artifacts`에 검사한 문서 세 개의 크기와 SHA-256이 들어 있습니다. 실행 기록 폴더의 `artifacts/docs/`에 검사 당시의 문서가 복사되어 있습니다.

## 4. 보존한 문서를 확인하기

```sh
awkit review verify <run_dir>
```

`<run_dir>` 자리에 앞 단계 결과의 `run_dir` 값을 넣습니다. 보존한 파일이 검사 당시와 같으면 모든 항목이 `ok`이고 종료 코드는 `0`입니다. 보존 폴더의 파일을 하나 고치고 다시 실행하면 그 파일이 `changed`로 나옵니다.

## 다음에 할 일

고친 문서를 commit하고, 같은 방식으로 자기 문서 폴더에 적용합니다. `checks.toml`의 검사 명령을 프로젝트의 링크 검사나 렌더링 명령으로 바꾸고, `artifacts`에 보존할 파일을 적으면 됩니다. 에이전트에게 맡길 때는 [project.md](project.md)를 채워 작업 전에 읽게 하세요. 한국어 문서를 쓰거나 고칠 때는 키트의 Korean Writing Guide를 함께 읽게 합니다.
