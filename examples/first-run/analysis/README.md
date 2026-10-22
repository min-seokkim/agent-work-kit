# 분석 예제

센서 원시값에서 최대 가속도를 계산하는 과정을 검사와 함께 해 봅니다. 분석에는 측정값 외에 환산 계수와 표본 주기 같은 가정이 들어가는데, 이 예제의 가정 파일에는 실제 데이터와 맞지 않는 값이 하나 있어 첫 검사는 실패합니다. 가정을 고친 뒤 다시 검사하면 보고서가 만들어지고, 보고서는 관측값, 계산값, 가정, 해석을 따로 적습니다.

| 파일 | 역할 |
|---|---|
| `input/readings.csv` | 센서 원시값. 시각(초)과 ADC 카운트입니다. |
| `assumptions.toml` | 환산 계수, 중력 가속도, 표본 주기. 표본 주기가 데이터와 다릅니다. |
| `analyze.py` | 가정을 데이터와 대조한 뒤 `output/report.json`을 만듭니다. |
| `check_report.py` | 보고서의 구조를 확인하고 계산값을 입력에서 다시 계산해 대조합니다. |
| `checks.toml` | 준비 단계로 `analyze.py`, 검사 단계로 `check_report.py`를 실행하고 입력, 가정, 보고서를 보존합니다. |
| `project.md` | 이 예제의 프로젝트 적용표 |

Python 3.11 이상, Git, `awkit`이 필요합니다. 아래 명령은 이 폴더에서 실행합니다.

## 1. Git 저장소로 만들기

```sh
git init
git add -A
git commit -m "Start the analysis example"
```

## 2. 실패를 확인하기

```sh
awkit review check "$(git rev-parse HEAD)" --config checks.toml --runs-root .awkit/reviews
```

PowerShell에서는 `(git rev-parse HEAD)`로 commit을 넘깁니다. 결과의 `status`는 `failed`입니다. 실행 기록 폴더의 `01.log`에 가정한 표본 주기와 데이터에서 관측한 간격이 다르다고 나옵니다. 분석 스크립트는 가정이 데이터와 어긋나면 계산을 시작하지 않습니다.

## 3. 고치고 다시 검사하기

`assumptions.toml`의 `sample_rate_hz`를 로그가 알려 준 관측값에 맞게 고칩니다. 고친 파일만 담은 스냅샷을 만들어 검사합니다.

```sh
snap=$(awkit review snapshot assumptions.toml)
awkit review check "$snap" --config checks.toml --runs-root .awkit/reviews
```

이번에는 `status`가 `passed`입니다. 실행 기록 폴더의 `artifacts/output/report.json`을 열면 네 부분이 있습니다.

| 부분 | 내용 |
|---|---|
| `observed` | 입력에서 직접 읽은 값. 표본 수, 관측한 표본 간격, 최대 카운트 |
| `assumptions` | 계산에 쓴 가정과 그 출처 파일 |
| `computed` | 가정을 적용해 계산한 값. 최대 가속도(g, m/s²) |
| `interpretation` | 사람이 적는 해석. 스크립트는 `null`로 두고 `unverified`로 표시합니다. |

검사 스크립트는 `computed`를 입력과 가정에서 다시 계산해 대조하고, `interpretation`이 계산값처럼 채워져 있지 않은지 확인합니다.

## 4. 채택하고 나중에 비교하기

보고서가 맞다고 판단했다면 그 실행을 채택본으로 남깁니다.

```sh
awkit review accept <run_dir>
```

이후 입력이나 가정을 바꿔 다시 분석했을 때, 그 실행의 결과가 채택본과 어디가 달라졌는지 봅니다.

```sh
awkit review compare --run <새 run_dir> --diff
```

같은 입력과 가정이면 모두 `same`이고, 달라진 파일은 `changed`와 함께 diff가 나옵니다. 어떤 입력과 가정에서 어떤 결과가 나왔는지 대조할 수 있습니다.

## 다음에 할 일

자기 분석에 적용할 때는 `analyze.py`를 실제 분석 명령으로 바꾸되 세 가지는 유지하세요. 가정을 파일로 두고 데이터와 대조하는 것, 보고서에서 관측값·가정·계산값·해석을 나누는 것, 해석은 사람이 적고 검사가 그것을 계산값과 혼동하지 않게 하는 것입니다.
