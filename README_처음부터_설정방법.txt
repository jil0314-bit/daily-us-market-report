# 텔레그램 아침 매매 브리핑 자동 발송

형이 받을 내용:

- 미국 증시와 한국시장 영향
- 국내 급등주·테마주
- 경제지표·금리·환율
- AI·반도체·기술 뉴스
- 뉴스 5개 + 한 줄 매매 해석

매일 오전 6:30 한국시간에 텔레그램으로 자동 발송됩니다.

---

## 1단계. GitHub에 새 저장소 만들기

1. GitHub 홈페이지에 들어갑니다.
2. 오른쪽 위 `+` 버튼을 누릅니다.
3. `New repository`를 누릅니다.
4. Repository name에 아래처럼 입력합니다.

```text
telegram-daily-market-report
```

5. `Public` 또는 `Private` 아무거나 선택해도 됩니다.
6. 아래쪽 초록색 `Create repository` 버튼을 누릅니다.

---

## 2단계. 이 폴더 안의 파일을 GitHub에 올리기

올릴 파일은 총 3개와 폴더 1개입니다.

```text
market_report.py
requirements.txt
.github/workflows/daily_telegram_report.yml
```

GitHub 저장소 화면에서:

1. 가운데 또는 오른쪽 위의 `Add file`을 누릅니다.
2. `Upload files`를 누릅니다.
3. 이 폴더 안의 파일들을 끌어다 놓습니다.
4. 아래 초록색 `Commit changes` 버튼을 누릅니다.

주의:
`.github/workflows/daily_telegram_report.yml` 파일은 폴더 구조가 중요합니다.
반드시 `.github` 폴더 안의 `workflows` 폴더 안에 들어가야 자동 실행됩니다.

---

## 3단계. 텔레그램 비밀값 2개 넣기

GitHub 저장소 화면에서:

1. 위쪽 탭에서 `Settings`를 누릅니다.
2. 왼쪽 메뉴에서 `Secrets and variables`를 누릅니다.
3. 그 아래 `Actions`를 누릅니다.
4. 오른쪽 위 `New repository secret` 버튼을 누릅니다.

첫 번째 비밀값:

Name:

```text
TELEGRAM_BOT_TOKEN
```

Secret:

```text
형의 텔레그램 봇 토큰
```

넣고 `Add secret`을 누릅니다.

두 번째 비밀값도 똑같이 만듭니다.

Name:

```text
TELEGRAM_CHAT_ID
```

Secret:

```text
형의 텔레그램 채팅방 ID
```

넣고 `Add secret`을 누릅니다.

---

## 4단계. 바로 테스트 실행하기

1. GitHub 저장소 위쪽 탭에서 `Actions`를 누릅니다.
2. 왼쪽에서 `Daily Telegram Market Report`를 누릅니다.
3. 오른쪽에 `Run workflow` 버튼을 누릅니다.
4. 초록색 `Run workflow` 버튼을 한 번 더 누릅니다.

성공하면 텔레그램 방에 브리핑이 옵니다.

---

## 5단계. 자동 실행 시간

이 파일은 아래 시간에 자동 실행됩니다.

```text
매일 오전 6:30 한국시간
```

GitHub Actions는 UTC 시간을 쓰기 때문에 코드에는 이렇게 들어가 있습니다.

```text
30 21 * * *
```

이 뜻은:

```text
UTC 밤 9시 30분 = 한국시간 다음날 아침 6시 30분
```

---

## 오류가 날 때 가장 먼저 볼 것

### 1. 텔레그램 메시지가 안 오면

- 봇에게 `/start`를 보냈는지 확인
- TELEGRAM_BOT_TOKEN 오타 확인
- TELEGRAM_CHAT_ID 오타 확인

### 2. GitHub Actions가 빨간색이면

1. GitHub에서 `Actions` 클릭
2. 실패한 실행 기록 클릭
3. `Send Telegram report` 부분 클릭
4. 빨간 글씨 오류를 확인

### 3. 파일 위치가 틀리면 자동 실행이 안 됩니다

정확한 위치:

```text
.github/workflows/daily_telegram_report.yml
```

폴더 이름과 파일 이름이 조금이라도 틀리면 안 됩니다.
