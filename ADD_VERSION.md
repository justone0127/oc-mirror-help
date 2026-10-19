# OCP 버전 추가 / 갱신 절차

웹 페이지의 **OCP 버전 목록은 `data/` 폴더에 있는 버전을 그대로 보여줍니다.**
새 버전(이전 버전 포함)을 추가할 때 코드 수정은 필요 없고, 데이터를 수집해서 GitHub에 push 하면 됩니다.

- 사이트: https://justone0127.github.io/oc-mirror-help/
- 저장소: https://github.com/justone0127/oc-mirror-help

---

## 1. 사전 준비 (최초 1회)

인터넷이 되는 PC/서버에서 진행합니다.

| 항목 | 확인 방법 | 비고 |
|---|---|---|
| `oc` CLI | `oc version --client` | 카탈로그 이미지 추출(`oc image extract`)에 사용 |
| `python3` | `python3 --version` | 데이터 변환 |
| PyYAML | `python3 -c "import yaml"` | 없으면 `pip install pyyaml` — 없으면 quay 등 일부 오퍼레이터가 누락됨 |
| Red Hat 레지스트리 로그인 | `podman login registry.redhat.io` | 또는 pull-secret 파일 사용 (`AUTH=~/pull-secret.json`) |
| 저장소 | `git clone https://github.com/justone0127/oc-mirror-help.git` | 이미 있으면 `git pull` 로 최신화 |

```bash
cd oc-mirror-help
git pull
```

---

## 2. (선택) 카탈로그 이미지가 있는지 먼저 확인

추가하려는 버전의 카탈로그 이미지가 존재하는지, 언제 빌드됐는지만 빠르게 확인합니다.

```bash
./collect.sh --check 4.18 4.19
./collect.sh --check -c all 4.18      # marketplace 까지 확인
```

`(없음/인증실패)` 로 나오면 해당 버전 이미지가 없거나 로그인이 안 된 상태입니다.

---

## 3. 데이터 수집

```bash
# 예: 4.18, 4.19 추가 (Red Hat / Certified / Community 카탈로그 + OCP 릴리스 정보)
./collect.sh 4.18 4.19

# 필요한 카탈로그만
./collect.sh -c "redhat certified" 4.18

# pull-secret 파일로 인증
AUTH=~/pull-secret.json ./collect.sh 4.18
```

- 버전당 약 3~6분 (카탈로그 1개당 1~2분)
- 결과: `data/<버전>/redhat.js`, `certified.js`, `community.js`, `releases.js` 생성, `data/index.js` 자동 갱신
- 기존 버전(4.20~4.22) 데이터는 건드리지 않습니다. 지정한 버전만 추가/덮어씁니다.

수집 결과 확인:

```bash
ls data/
tail -1 data/index.js        # window.OCM_RELEASES = ["4.18", "4.19", "4.20", ...]
```

---

## 4. 로컬에서 확인

```bash
open index.html              # macOS
# 또는
python3 -m http.server 8080  # → http://localhost:8080
```

- 상단 **OCP 버전** 목록에 새 버전이 보이는지
- 새 버전 선택 시 오퍼레이터 목록과 카탈로그 칩 숫자가 나오는지
- ImageSetConfiguration 탭에서 릴리스 버전 목록이 나오는지

---

## 5. GitHub 에 반영

```bash
git add data
git commit -m "Add OCP 4.18, 4.19 catalog data"
git push
```

push 후 1~2분 뒤 사이트에 반영됩니다.
- 진행 상황: 저장소 **Actions** 탭 → `pages build and deployment`
- 화면이 바뀌지 않으면 브라우저 강력 새로고침 (**Cmd+Shift+R** / Ctrl+Shift+R)

---

## 기존 버전 데이터 갱신

오퍼레이터 채널·버전이 추가됐거나 새 OCP 패치 릴리스가 나왔을 때도 같은 방법입니다.

```bash
./collect.sh 4.22                    # 카탈로그 + 릴리스 정보 다시 수집
./collect.sh --releases-only 4.22    # OCP 릴리스(패치 버전/업그레이드 경로)만 갱신 — 빠름, 로그인 불필요
git add data && git commit -m "Refresh OCP 4.22 data" && git push
```

## 버전 삭제

```bash
rm -rf data/4.18
python3 build_data.py index          # data/index.js 다시 생성
git add -A data && git commit -m "Remove OCP 4.18 data" && git push
```

---

## 문제 해결

| 증상 | 원인 / 조치 |
|---|---|
| `[SKIP] 추출 실패` | 해당 버전 이미지가 없거나 인증 실패 → `podman login registry.redhat.io` 또는 `AUTH=` 지정 후 재시도 |
| `[WARN] PyYAML 없음` | `pip install pyyaml` 후 다시 수집 (quay 관련 오퍼레이터 누락 방지) |
| 새 버전이 목록에 안 보임 | `data/index.js` 가 커밋됐는지 확인 (`git status`), 강력 새로고침 |
| 릴리스 버전 목록이 비어 있음 | `./collect.sh --releases-only <버전>` 실행 (api.openshift.com 접속 필요) |
| `eus-<버전>` 채널이 없음 | 정상 — EUS 채널은 짝수 버전(4.18, 4.20, 4.22 …)에만 있습니다 |
| marketplace 카탈로그 없음 | 일부 버전은 `redhat-marketplace-index` 가 제공되지 않습니다 |
