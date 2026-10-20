# Operator Mirror Picker

폐쇄망 OpenShift 설치 준비용 페이지입니다. OCP 버전별 Operator 카탈로그(Red Hat / Certified / Community)를 한 화면에서 검색하고,
필요한 Operator·채널·버전을 고르면 `oc-mirror --v2` 용 **ImageSetConfiguration**, **엑셀(CSV)**, **이름 목록**, **명령어**를 바로 복사할 수 있습니다.

## 구성

| 파일 | 역할 |
|---|---|
| `index.html` | 웹 페이지 (외부 라이브러리 없음, `file://` 로 열어도 동작) |
| `collect.sh` | 카탈로그 이미지에서 `/configs`(FBC)를 추출해 `data/` 생성 |
| `build_data.py` | FBC 디렉터리 또는 `oc-mirror list` 결과(.out)를 `data/<버전>/<카탈로그>.js` 로 변환, OCP 릴리스 그래프를 `data/<버전>/releases.js` 로 저장 |
| `data/` | 생성된 데이터 (`index.js` 가 목록) |
| `data/presets.js` | 기능별 오퍼레이터 묶음과 운영상 의존성 (손으로 편집) |
| `data/rhoai.js` | RHOAI 버전별 추가 이미지 (`./collect.sh --rhoai`) |

## 데이터 수집 (인터넷 되는 서버)

```bash
podman login registry.redhat.io            # 또는 AUTH=~/pull-secret.json
./collect.sh 4.22                           # 기본: redhat, certified, community
./collect.sh 4.20 4.21 4.22                 # 여러 버전 (버전 비교 탭에서 활용)

# 카탈로그 소스 지정 (-c, 공백 구분)
./collect.sh -c "redhat community" 4.22
./collect.sh -c all 4.22                    # + redhat-marketplace-index
./collect.sh -c "registry.redhat.io/redhat/community-operator-index" 4.22    # 이미지 주소 (태그 생략 시 :v<버전>)
./collect.sh -c "partner=quay.io/myorg/partner-index:v{v}" 4.22              # 이름=이미지, {v} → 버전

# OCP 릴리스 버전/업그레이드 경로만 갱신 (api.openshift.com, 인증 불필요 · collect.sh 실행 시 자동 포함)
./collect.sh --releases-only 4.22

# RHOAI 버전별 추가 이미지(노트북·파이프라인 런타임·학습 이미지) 갱신 (GitHub, 인증 불필요)
./collect.sh --rhoai

# 추출 전에 카탈로그 이미지가 있는지/언제 빌드됐는지만 확인
./collect.sh --check -c all 4.21 4.22
```

| 키 | 카탈로그 이미지 |
|---|---|
| `redhat` | `registry.redhat.io/redhat/redhat-operator-index:v<버전>` |
| `certified` | `registry.redhat.io/redhat/certified-operator-index:v<버전>` |
| `community` | `registry.redhat.io/redhat/community-operator-index:v<버전>` |
| `marketplace` | `registry.redhat.io/redhat/redhat-marketplace-index:v<버전>` (4.22는 아직 없음) |

페이지에서는 카탈로그가 칩으로 표시되어 필요한 것만 켜고 끌 수 있고, 각 카탈로그의 소스 이미지·빌드 날짜가 함께 보입니다.
ImageSetConfiguration은 선택한 오퍼레이터를 카탈로그별 `- catalog:` 항목으로 묶어 생성합니다.

`oc-mirror list` 를 패키지마다 반복 실행하는 대신 카탈로그 이미지의 FBC를 직접 읽기 때문에
패키지·기본 채널뿐 아니라 **모든 채널, 채널별 head/버전 목록, deprecated 여부, disconnected 지원 여부**까지 한 번에 수집됩니다.
카탈로그당 1~2분 정도 걸립니다. PyYAML(`pip install pyyaml`)이 있어야 YAML 형식 패키지(quay 등)도 포함됩니다.

### 기존 방식(.out)도 사용 가능

```bash
oc-mirror --v2 list operators --catalog=registry.redhat.io/redhat/redhat-operator-index:v4.22 > package.out
python3 build_data.py out --ocp 4.22 --catalog redhat \
  --image registry.redhat.io/redhat/redhat-operator-index:v4.22 --src package.out
```

또는 페이지 상단 **.out 불러오기** 로 파일을 바로 열 수 있습니다(브라우저에서만 임시 로드). 카탈로그 이미지는 목록에서 고르거나 직접 입력할 수 있습니다.
이 방식은 이름·표시 이름·기본 채널만 있습니다.

## 사용

```bash
open index.html                 # 로컬에서 바로
python3 -m http.server 8080     # 팀에 공유할 때
```

- **OCP 버전** 선택 → 카탈로그 칩으로 필터 → 검색(`/` 단축키)
- 행 클릭: 채널 상세 (미러할 채널, minVersion/maxVersion 지정)
- **목록 붙여넣기**: 엑셀에 정리해 둔 오퍼레이터 이름(필요하면 `이름 채널`)을 붙여 넣어 한 번에 선택. 없는 이름은 따로 알려줍니다.
- 오른쪽 패널 탭
  - `ImageSetConfiguration` — `mirror.openshift.io/v2alpha1` 의 `imageset-config.yaml`
    - **OpenShift 릴리스**: 채널(stable/fast/eus/candidate)과 대상 버전을 실제 릴리스 목록에서 선택 (기본: 해당 마이너 최신).
      업그레이드할 경우 **시작 버전**(이전 마이너 포함)을 고르면 min/maxVersion + `shortestPath` 를 넣고 업그레이드 경로(예: 4.20.12 → 4.21.6 → 4.22.18)를 보여줍니다.
      아키텍처, `graph`, `kubeVirtContainer` 옵션
    - **파일 하나** 또는 **OCP / Operator 분리**(`imageset-config-ocp.yaml`, `imageset-config-operators.yaml`)
    - 선택 채널에 기본 채널이 없으면 `defaultChannel` 자동 추가, additionalImages 입력
  - `엑셀` — **복사**: 엑셀에 붙여넣으면 셀별로 들어감 · **CSV 다운로드**: `operators.csv` (UTF-8 BOM, 엑셀에서 한글 깨짐 없음)
  - `이름 목록`, `명령어`(oc-mirror 실행/확인 명령)
  - `버전 비교` — 수집된 모든 OCP 버전에서 선택한 오퍼레이터의 기본 채널/head 비교 (업그레이드 계획용)
- **도구 다운로드**: OCP 버전·서버 OS(RHEL 9/8, macOS, Windows)·아키텍처에 맞는 `oc-mirror`, `oc`, `openshift-install`, `opm`, `mirror-registry` 다운로드 링크와
  `curl` 다운로드·설치 명령을 한 번에 복사 (mirror.openshift.com)
  - mirror-registry 설치 옵션 입력: 호스트명:포트, 관리자 ID/비밀번호, `--quayRoot`(설치/설정), `--quayStorage`(이미지), `--sqliteStorage`(DB),
    SSL 인증서/키, 원격 설치(-H/-u/-k) → 사전 조건·설치·인증서 신뢰·로그인 확인 명령 생성 (비밀번호는 브라우저에 저장하지 않음)
- **기능별 묶음**: RHOAI 3.x / OpenShift Virtualization / Service Mesh 3.x / OPP 처럼 기능 단위로 필요한 오퍼레이터를 그룹별로 체크해 한 번에 선택
  - 오퍼레이터마다 미러링할 **채널 선택** (기본: default 채널, 채널별 head 버전·의존성 표시)
  - 현재 OCP 버전 카탈로그에 없는 오퍼레이터는 표시만 되고 선택되지 않음
  - RHOAI: 버전(예: 3.5.1)을 고르면 [rhoai-disconnected-install-helper](https://github.com/red-hat-data-services/rhoai-disconnected-install-helper) 의
    노트북/파이프라인 런타임/학습 이미지를 종류·가속기(CPU/CUDA/ROCm)·Python 버전으로 걸러 `additionalImages` 에 추가하고, `rhods-operator` 채널/버전도 맞춤
  - MaaS·TrustyAI·Model Registry 용 DB 이미지(PostgreSQL, MySQL) 선택 추가
- **의존성 확인**: 선택한 오퍼레이터의 의존성을 오른쪽 패널에서 자동 확인
  - 카탈로그에 선언된 OLM 의존성(`olm.package.required`, `olm.gvk.required`, 채널 head 번들 기준)을 끝까지 따라가 **누락**을 표시
    (예: `rhcl-operator` → authorino / limitador / dns-operator, `odf-dependencies` → cephcsi, rook-ceph, ocs, mcg …)
  - 요구 버전이 미러될 버전(기본은 채널 head)과 맞지 않으면 **버전 불일치** 표시 → 맞는 채널/`minVersion` 으로 수정
  - OLM 에 선언되지 않은 운영상 의존성(예: ACM → MCE, odf-operator → odf-dependencies, GPU Operator → NFD)은 **권장**으로 표시
  - **추가 / 모두 추가·수정** 버튼으로 바로 반영. 표의 `의존 N` 태그와 행 상세에서도 채널별 의존성 확인
- 선택은 브라우저에 자동 저장되며, **링크** 버튼으로 선택 상태가 담긴 URL을 공유할 수 있습니다.

## 기능별 묶음(프리셋) 편집

`data/presets.js` 만 고치면 됩니다 (코드 수정 불필요, push 하면 사이트에 반영).

```js
{
  id: 'mypreset', name: '표시 이름', desc: '설명',
  groups: [
    { name: '코어', items: [
      { n: 'rhods-operator', note: '설명' },                  // 패키지 이름
      { n: 'gpu-operator-certified', c: 'certified' },        // 카탈로그 지정 (생략 시 redhat → certified → community)
      { n: 'lvms-operator', off: true },                      // 기본 체크 해제
      { n: 'odf-operator', ch: 'stable-4.22' },               // 기본으로 고를 채널 (생략 시 default 채널, 창에서 변경 가능)
    ] },
  ],
  images: [ { ref: 'registry.redhat.io/rhel9/postgresql-16:latest', note: '용도', off: true } ],
}
```

OLM 에 선언되지 않은 의존성은 같은 파일의 `OCM_SOFT_DEPS` 에 `'패키지': [{ n: '필요한 패키지', why: '이유' }]` 형식으로 추가합니다.

## 버전 추가 / 데이터 갱신

이전 버전 추가, 기존 버전 갱신, 삭제 절차는 [ADD_VERSION.md](ADD_VERSION.md) 를 참고하세요.
