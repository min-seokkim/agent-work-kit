# 데이터 예제

주문 CSV를 가공해 품목별 요약을 만드는 과정을 검사와 함께 해 봅니다. 입력 파일에는 일부러 잘못된 열 이름이 있어 첫 검사는 실패합니다. 입력을 고친 뒤 다시 검사하면 가공 결과가 만들어지고, 입력과 결과가 해시와 함께 보존됩니다.

| 파일 | 역할 |
|---|---|
| `input/orders.csv` | 입력 데이터. `quantity` 열이 `qty`로 적혀 있습니다. |
| `process.py` | 입력 열을 검사하고 `output/summary.csv`를 만듭니다. |
| `check_output.py` | 요약의 열과 합계를 입력에서 다시 계산해 대조합니다. |
| `checks.toml` | 준비 단계로 `process.py`를, 검사 단계로 `check_output.py`를 실행하고 입력과 결과를 보존합니다. |
| `project.md` | 이 예제의 프로젝트 적용표 |

Python 3.11 이상, Git, `awkit`이 필요합니다. 아래 명령은 이 폴더에서 실행합니다.

## 1. Git 저장소로 만들기

```sh
git init
git add -A
git commit -m "Start the data example"
```

## 2. 실패를 확인하기

```sh
awkit review check "$(git rev-parse HEAD)" --config checks.toml --runs-root .awkit/reviews
```

PowerShell에서는 `(git rev-parse HEAD)`로 commit을 넘깁니다. 결과의 `status`는 `failed`입니다. 준비 단계인 `process`가 실패했으므로 검사 단계는 실행되지 않았고, `missing_artifacts`에 `output/summary.csv`가 있습니다. 실행 기록 폴더의 `01.log`에 어떤 열이 없는지 나옵니다.

## 3. 고치고 다시 검사하기

`input/orders.csv`의 첫 줄에서 `qty`를 `quantity`로 바꿉니다. 고친 입력만 담은 스냅샷을 만들어 검사합니다.

```sh
snap=$(awkit review snapshot input/orders.csv)
awkit review check "$snap" --config checks.toml --runs-root .awkit/reviews
```

이번에는 `status`가 `passed`입니다. `artifacts`에 입력 파일과 `output/summary.csv`의 크기와 SHA-256이 있고, 실행 기록 폴더의 `artifacts/`에 두 파일이 복사되어 있습니다. 요약 파일은 worktree에서 만들어졌으므로 작업 폴더에는 생기지 않습니다. 작업 폴더에서 직접 보려면 `python process.py`를 실행하세요.

## 4. 보존한 결과를 확인하기

```sh
awkit review verify <run_dir>
```

입력과 결과가 검사 당시 그대로이면 모두 `ok`입니다. 같은 입력으로 다시 검사하면 같은 해시가 나오므로, 나중에 어떤 입력에서 어떤 결과가 나왔는지 대조할 수 있습니다.

## 다음에 할 일

자기 데이터에 적용할 때는 `process.py`를 실제 가공 명령으로, `check_output.py`를 결과 검사 명령으로 바꾸고 `checks.toml`의 `artifacts`에 보존할 입력과 결과를 적습니다. 입력 파일이 크거나 외부에 있으면 파일 대신 입력의 식별자와 해시를 남기는 명령을 넣으세요.
