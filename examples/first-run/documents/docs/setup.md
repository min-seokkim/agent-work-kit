# 설치

메모 앱은 Python 3.11 이상에서 동작합니다. 가상환경을 만들고 패키지를 설치하세요.

```sh
python -m venv .venv
.venv/bin/pip install memo-app
```

## 설정 항목

설정 파일 `memo.toml`은 홈 폴더에 둡니다.

| 항목 | 뜻 | 기본값 |
|---|---|---|
| `folder` | 메모를 저장할 폴더 | `~/memo` |
| `editor` | 메모를 열 때 사용할 편집기 | 운영체제 기본값 |

설정을 바꾼 뒤에는 앱을 다시 시작합니다. 사용 방법은 [사용 안내](guide.md)에 있습니다.
