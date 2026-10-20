#!/usr/bin/env bash
# 인터넷이 되는 서버에서 OCP 버전별 Operator 카탈로그를 추출해 웹 페이지용 데이터(data/)를 만든다.
#
#   ./collect.sh 4.22                          # 기본: redhat certified community
#   ./collect.sh 4.20 4.21 4.22
#   ./collect.sh -c "redhat community" 4.22     # 필요한 카탈로그만
#   ./collect.sh -c all 4.22                    # redhat certified community marketplace
#   ./collect.sh -c "registry.redhat.io/redhat/community-operator-index" 4.22   # 이미지 주소 (태그 생략 시 :v<버전>)
#   ./collect.sh -c "mycat=quay.io/myorg/my-index:v{v}" 4.22                     # 이름=이미지, {v} 는 버전으로 치환
#   ./collect.sh --check 4.21 4.22              # 카탈로그 이미지 존재 여부/생성일만 확인
#
#   ./collect.sh --releases-only 4.22           # OCP 릴리스 버전/업그레이드 경로만 갱신 (api.openshift.com)
#   ./collect.sh --rhoai                        # RHOAI 버전별 추가 이미지(노트북 등)만 갱신 (GitHub, 인증 불필요)
#
# 환경변수: CATALOGS(-c 와 동일), AUTH(인증 파일), ARCH(기본 linux/amd64), PYTHON, RELEASES=0(릴리스 정보 생략), RHOAI_MIN(기본 2.25)
# 필요: oc (oc image extract/info), python3 (+ PyYAML 권장: 일부 패키지가 catalog.yaml 형식)
set -euo pipefail

cd "$(dirname "$0")"
usage() { sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

CATALOGS=${CATALOGS:-"redhat certified community"}
CHECK=0
RELEASES=${RELEASES:-1}
RELEASES_ONLY=0
RHOAI_ONLY=0
VERSIONS=()
while [ $# -gt 0 ]; do
  case "$1" in
    -c|--catalogs) CATALOGS=$2; shift 2 ;;
    --check)       CHECK=1; shift ;;
    --releases-only) RELEASES_ONLY=1; shift ;;
    --rhoai)       RHOAI_ONLY=1; shift ;;
    -h|--help)     usage ;;
    -*)            echo "알 수 없는 옵션: $1"; usage 1 ;;
    *)             VERSIONS+=("${1#v}"); shift ;;
  esac
done
if [ $RHOAI_ONLY = 1 ]; then
  ${PYTHON:-python3} build_data.py rhoai --min "${RHOAI_MIN:-2.25}"
  [ ${#VERSIONS[@]} -ge 1 ] || exit 0
fi
[ ${#VERSIONS[@]} -ge 1 ] || usage 1
CATALOGS=" $CATALOGS "; CATALOGS=${CATALOGS// all / redhat certified community marketplace }

ARCH=${ARCH:-linux/amd64}
PYTHON=${PYTHON:-python3}
if [ -z "${AUTH:-}" ]; then
  for f in "${REGISTRY_AUTH_FILE:-}" "${XDG_RUNTIME_DIR:-/nonexistent}/containers/auth.json" \
           "$HOME/.config/containers/auth.json" "$HOME/.docker/config.json"; do
    [ -n "$f" ] && [ -f "$f" ] && { AUTH=$f; break; }
  done
fi
AUTH_ARGS=()
[ -n "${AUTH:-}" ] && AUTH_ARGS=(-a "$AUTH") && echo "auth: $AUTH"

# 카탈로그 지정값 → "키 이미지"
resolve() {
  local spec=$1 v=$2 key img
  case "$spec" in
    redhat|certified|community) key=$spec; img="registry.redhat.io/redhat/$spec-operator-index:v$v" ;;
    marketplace)                key=$spec; img="registry.redhat.io/redhat/redhat-marketplace-index:v$v" ;;
    *=*)                        key=${spec%%=*}; img=${spec#*=} ;;
    */*)                        img=$spec
                                key=${img##*/}; key=${key%%[:@]*}
                                key=${key%-operator-index}; key=${key%-index}
                                [ "$key" = redhat-marketplace ] && key=marketplace ;;
    *) echo "잘못된 카탈로그 지정: $spec" >&2; return 1 ;;
  esac
  img=${img//\{v\}/$v}
  # 태그/다이제스트가 없으면 :v<버전>
  local last=${img##*/}
  [[ "$last" == *:* || "$img" == *@* ]] || img="$img:v$v"
  echo "$key $img"
}

image_meta() {  # digest created
  oc image info "$1" "${AUTH_ARGS[@]}" --filter-by-os "$ARCH" -o json 2>/dev/null \
    | $PYTHON -c 'import json,sys; d=json.load(sys.stdin); print(d.get("digest",""), d.get("config",{}).get("created",""))' 2>/dev/null
}

if [ $CHECK = 1 ]; then
  printf '%-8s %-12s %-22s %s\n' OCP KEY CREATED IMAGE
  for v in "${VERSIONS[@]}"; do for spec in $CATALOGS; do
    read -r key img < <(resolve "$spec" "$v")
    if m=$(image_meta "$img") && [ -n "$m" ]; then
      printf '%-8s %-12s %-22s %s\n' "$v" "$key" "${m#* }" "$img"
    else
      printf '%-8s %-12s %-22s %s\n' "$v" "$key" "(없음/인증실패)" "$img"
    fi
  done; done
  exit 0
fi

if [ $RELEASES = 1 ] || [ $RELEASES_ONLY = 1 ]; then
  for v in "${VERSIONS[@]}"; do
    $PYTHON build_data.py releases --ocp "$v" --arch "${ARCH#*/}" || echo "   [WARN] $v 릴리스 정보 수집 실패"
  done
fi
[ $RELEASES_ONLY = 1 ] && exit 0

$PYTHON -c 'import yaml' 2>/dev/null || echo "[WARN] PyYAML 없음 → catalog.yaml 형식 패키지는 누락됩니다 (pip install pyyaml)"
WORK=${WORK:-$(mktemp -d -t ocm-catalog.XXXXXX)}

for v in "${VERSIONS[@]}"; do
  for spec in $CATALOGS; do
    read -r key img < <(resolve "$spec" "$v")
    dir="$WORK/$v-$key"
    echo "== [$key] $img"
    rm -rf "$dir"; mkdir -p "$dir"
    if ! oc image extract "$img" "${AUTH_ARGS[@]}" --filter-by-os "$ARCH" --path "/configs/:$dir" --confirm >/dev/null; then
      echo "   [SKIP] 추출 실패 (이미지가 없거나 인증 문제)"; continue
    fi
    m=$(image_meta "$img" || true)
    $PYTHON build_data.py fbc --ocp "$v" --catalog "$key" --image "$img" --src "$dir" \
      --digest "${m%% *}" --created "${m#* }"
    rm -rf "$dir"
  done
done
rmdir "$WORK" 2>/dev/null || true
echo
echo "완료. index.html 을 브라우저로 열거나, 디렉터리를 웹 서버로 공유하세요:"
echo "  python3 -m http.server 8080"
