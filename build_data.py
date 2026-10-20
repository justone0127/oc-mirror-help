#!/usr/bin/env python3
"""Operator 카탈로그(FBC) 또는 oc-mirror list 출력(.out)을 웹 페이지용 데이터로 변환한다.

사용 예:
  # 카탈로그 이미지에서 추출한 /configs 디렉터리 변환 (채널/버전까지 모두 포함)
  python3 build_data.py fbc --ocp 4.22 --catalog redhat \
      --image registry.redhat.io/redhat/redhat-operator-index:v4.22 --src ./configs

  # 기존 방식: oc-mirror --v2 list operators --catalog=... > package.out 결과 변환
  python3 build_data.py out --ocp 4.22 --catalog redhat \
      --image registry.redhat.io/redhat/redhat-operator-index:v4.22 --src package.out

  # OpenShift 릴리스 버전/업그레이드 그래프 (api.openshift.com, 인증 불필요)
  python3 build_data.py releases --ocp 4.22 --arch amd64

  # RHOAI 버전별 추가 이미지(노트북/파이프라인 런타임 등) - rhoai-disconnected-install-helper 저장소
  python3 build_data.py rhoai --min 2.25

  # data/index.js 만 다시 생성
  python3 build_data.py index

결과물:
  data/<ocp>/<catalog>.js   window.OCM.load(...) 호출 (file:// 로 열어도 동작)
  data/<ocp>/<catalog>.meta.json
  data/<ocp>/releases.js    OCP 릴리스 채널별 버전 + 업그레이드 경로
  data/rhoai.js             RHOAI 버전별 additionalImages
  data/index.js             사용 가능한 버전/카탈로그 목록
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request

try:
    import yaml  # PyYAML: catalog.yaml 형식 카탈로그 파싱용 (없으면 해당 파일은 건너뜀)
except ImportError:
    yaml = None

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")

CATALOG_LABELS = {
    "redhat": "Red Hat",
    "certified": "Certified",
    "community": "Community",
    "marketplace": "Marketplace",
}


# ---------------------------------------------------------------- version utils
def _vkey(v):
    """semver 비슷한 문자열 정렬 키. 1.10.0 > 1.9.0, 1.0.0 > 1.0.0-rc1"""
    v = (v or "").lstrip("v")
    main, _, pre = v.partition("-")
    main, _, _build = main.partition("+")
    nums = []
    for p in main.split("."):
        m = re.match(r"(\d+)(.*)", p)
        nums.append((int(m.group(1)), m.group(2)) if m else (-1, p))
    pre_key = (1,) if not pre else (0, tuple((0, int(x), "") if x.isdigit() else (1, 0, x) for x in re.split(r"[.]", pre)))
    return (nums, pre_key)


def sort_versions(vs):
    return sorted(set(v for v in vs if v), key=_vkey)


# ---------------------------------------------------------------- FBC parsing
def iter_docs(path):
    if path.endswith(".json"):
        with open(path, encoding="utf-8") as f:
            s = f.read()
        dec = json.JSONDecoder()
        i, n = 0, len(s)
        while i < n:
            while i < n and s[i].isspace():
                i += 1
            if i >= n:
                break
            obj, i = dec.raw_decode(s, i)
            yield obj
    elif path.endswith((".yaml", ".yml")):
        if yaml is None:
            print(f"  [WARN] PyYAML 없음 - 건너뜀: {path} (pip install pyyaml)", file=sys.stderr)
            return
        with open(path, encoding="utf-8") as f:
            loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
            for obj in yaml.load_all(f, Loader=loader):
                if obj:
                    yield obj


def load_fbc(src):
    pkgs, channels, bundles, deprecations = {}, [], {}, []
    for root, _dirs, files in os.walk(src):
        for fn in files:
            if not fn.endswith((".json", ".yaml", ".yml")):
                continue
            for o in iter_docs(os.path.join(root, fn)):
                schema = o.get("schema")
                if schema == "olm.package":
                    pkgs[o["name"]] = o
                elif schema == "olm.channel":
                    channels.append(o)
                elif schema == "olm.bundle":
                    bundles[(o.get("package"), o.get("name"))] = o
                elif schema == "olm.deprecations":
                    deprecations.append(o)
    return pkgs, channels, bundles, deprecations


def bundle_info(b):
    info = {"version": None, "csv": {}, "maxOCP": None, "req": [], "gvkreq": [], "gvk": []}
    for p in b.get("properties", []) or []:
        t, v = p.get("type"), p.get("value")
        if t == "olm.package" and isinstance(v, dict):
            info["version"] = v.get("version")
        elif t == "olm.package.required" and isinstance(v, dict) and v.get("packageName"):
            info["req"].append((v["packageName"], str(v.get("versionRange") or "")))
        elif t in ("olm.gvk.required", "olm.gvk") and isinstance(v, dict) and v.get("kind"):
            info["gvkreq" if t == "olm.gvk.required" else "gvk"].append(f'{v.get("group", "")}/{v.get("version", "")}/{v["kind"]}')
        elif t == "olm.csv.metadata" and isinstance(v, dict):
            info["csv"] = v
        elif t == "olm.maxOpenShiftVersion":
            info["maxOCP"] = str(v)
    info["images"] = len(b.get("relatedImages") or [])
    return info


def channel_head(entries):
    names = [e["name"] for e in entries]
    replaced = set()
    for e in entries:
        if e.get("replaces"):
            replaced.add(e["replaces"])
        replaced.update(e.get("skips") or [])
    heads = [n for n in names if n not in replaced]
    return heads or names


def build_from_fbc(src):
    pkgs, channels, bundles, deprecations = load_fbc(src)
    binfo = {k: bundle_info(b) for k, b in bundles.items()}
    # olm.gvk.required 해석용: GVK -> 제공 패키지
    gvk_owner = {}
    for (pkg, _n), bi in binfo.items():
        for g in bi["gvk"]:
            gvk_owner.setdefault(g, set()).add(pkg)

    dep_pkg, dep_ch = {}, {}
    for d in deprecations:
        for e in d.get("entries") or []:
            ref = e.get("reference") or {}
            msg = (e.get("message") or "").strip()
            if ref.get("schema") == "olm.package":
                dep_pkg[d["package"]] = msg or "deprecated"
            elif ref.get("schema") == "olm.channel":
                dep_ch[(d["package"], ref.get("name"))] = msg or "deprecated"

    by_pkg = {}
    for c in channels:
        by_pkg.setdefault(c["package"], []).append(c)

    out = []
    for name in sorted(pkgs):
        p = pkgs[name]
        chs = []
        heads = {}
        for c in by_pkg.get(name, []):
            entries = c.get("entries") or []
            vers = [binfo.get((name, e["name"]), {}).get("version") for e in entries]
            head_names = channel_head(entries)
            head_vers = [(binfo.get((name, h), {}).get("version"), h) for h in head_names]
            head_vers.sort(key=lambda x: _vkey(x[0]))
            hv, hn = head_vers[-1] if head_vers else (None, None)
            heads[c["name"]] = hn
            ch = {"n": c["name"], "h": hv, "v": sort_versions(vers)}
            # head 번들의 OLM 의존성: rq = [[패키지, 버전 범위]], rg = [[group/version/Kind, 제공 패키지]]
            hb = binfo.get((name, hn), {})
            if hb.get("req"):
                ch["rq"] = [list(x) for x in sorted(set(hb["req"]))]
            if hb.get("gvkreq"):
                ch["rg"] = [[g, sorted(gvk_owner.get(g, set()) - {name})[0] if gvk_owner.get(g, set()) - {name} else ""]
                            for g in sorted(set(hb["gvkreq"]))]
            if (name, c["name"]) in dep_ch:
                ch["dep"] = dep_ch[(name, c["name"])]
            chs.append(ch)
        chs.sort(key=lambda c: _vkey(re.sub(r"^[^\d]*", "", c["n"]) or "0"))

        dc = p.get("defaultChannel")
        head = binfo.get((name, heads.get(dc)), {}) if dc else {}
        csv = head.get("csv") or {}
        ann = csv.get("annotations") or {}
        rec = {
            "n": name,
            "d": csv.get("displayName") or "",
            "p": ((csv.get("provider") or {}).get("name") or "") if isinstance(csv.get("provider"), dict) else "",
            "dc": dc or "",
            "ch": chs,
        }
        desc = (ann.get("description") or "").strip()
        if desc:
            rec["ds"] = desc[:240]
        cats = ann.get("categories")
        if cats:
            rec["cat"] = [c.strip() for c in cats.split(",") if c.strip()]
        disc = ann.get("features.operators.openshift.io/disconnected")
        if disc is None:
            infra = ann.get("operators.openshift.io/infrastructure-features") or ""
            if "disconnected" in infra.lower():
                disc = "true"
        if disc is not None:
            rec["disc"] = str(disc).lower() == "true"
        fips = ann.get("features.operators.openshift.io/fips-compliant")
        if fips is not None:
            rec["fips"] = str(fips).lower() == "true"
        if head.get("maxOCP"):
            rec["max"] = head["maxOCP"]
        if head.get("images"):
            rec["img"] = head["images"]
        if name in dep_pkg:
            rec["dep"] = dep_pkg[name]
        out.append(rec)
    return out, len(bundles)


# ---------------------------------------------------------------- .out parsing
def build_from_out(src):
    """oc-mirror (v1/v2) list operators --catalog 출력 파싱. 헤더 컬럼 위치 기준."""
    with open(src, encoding="utf-8", errors="replace") as f:
        lines = [l.rstrip("\n") for l in f]
    hdr_i = next((i for i, l in enumerate(lines) if re.match(r"^\s*NAME\s+DISPLAY NAME\s+DEFAULT CHANNEL", l)), None)
    if hdr_i is None:
        raise SystemExit(f"헤더(NAME / DISPLAY NAME / DEFAULT CHANNEL)를 찾을 수 없음: {src}")
    out = []
    for l in lines[hdr_i + 1:]:
        if not l.strip() or re.match(r"^\s*(\d{4}/\d\d/\d\d|\[|time=|I\d{4}|W\d{4})", l):
            continue
        # 패키지 이름과 채널 이름에는 공백이 없으므로 첫/마지막 토큰, 나머지는 표시 이름
        toks = l.split()
        if len(toks) < 2:
            continue
        name, dc = toks[0], toks[-1]
        disp = l.strip()[len(name):].rstrip()[: -len(dc)].strip()
        out.append({"n": name, "d": disp, "dc": dc, "ch": [{"n": dc, "h": None, "v": []}] if dc else []})
    out.sort(key=lambda r: r["n"])
    return out


# ---------------------------------------------------------------- writers
def write_catalog(ocp, catalog, image, packages, source, extra=None):
    d = os.path.join(DATA_DIR, ocp)
    os.makedirs(d, exist_ok=True)
    meta = {
        "ocp": ocp,
        "catalog": catalog,
        "label": CATALOG_LABELS.get(catalog, catalog),
        "image": image,
        "source": source,
        "count": len(packages),
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    meta.update(extra or {})
    body = json.dumps({"meta": meta, "packages": packages}, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(d, f"{catalog}.js"), "w", encoding="utf-8") as f:
        f.write(f"window.OCM&&window.OCM.load({body});\n")
    with open(os.path.join(d, f"{catalog}.meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"  -> data/{ocp}/{catalog}.js  ({len(packages)} packages)")


# ---------------------------------------------------------------- OCP releases
GRAPH_URL = "https://api.openshift.com/api/upgrades_info/v1/graph?channel={ch}&arch={arch}"
RELEASE_CHANNELS = ("stable", "fast", "eus", "candidate")


def fetch_releases(ocp, arch):
    """채널별 릴리스 버전 목록과 업그레이드 edge(버전 인덱스 쌍)."""
    chans = {}
    for t in RELEASE_CHANNELS:
        ch = f"{t}-{ocp}"
        req = urllib.request.Request(GRAPH_URL.format(ch=ch, arch=arch), headers={"Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                g = json.load(r)
        except Exception as e:  # 채널이 없거나 네트워크 문제
            print(f"  [WARN] {ch}: {e}", file=sys.stderr)
            continue
        nodes = [n["version"] for n in g.get("nodes", [])]
        if not nodes:
            continue
        vs = sort_versions(nodes)
        pos = {v: i for i, v in enumerate(vs)}
        edges = sorted({(pos[nodes[a]], pos[nodes[b]]) for a, b in g.get("edges", [])})
        # 조건부 업그레이드(알려진 위험이 있는 경로)는 별도 표시
        cond = set()
        for ce in g.get("conditionalEdges", []) or []:
            for e in ce.get("edges", []):
                if e.get("from") in pos and e.get("to") in pos:
                    cond.add((pos[e["from"]], pos[e["to"]]))
        chans[t] = {"v": vs, "e": [list(e) for e in edges], "c": [list(e) for e in sorted(cond)]}
        print(f"  {ch}: {len(vs)} releases, {len(edges)} edges, {len(cond)} conditional")
    return chans


def write_releases(ocp, arch):
    chans = fetch_releases(ocp, arch)
    if not chans:
        print(f"  [WARN] OCP {ocp} 릴리스 정보를 가져오지 못함", file=sys.stderr)
        return
    d = os.path.join(DATA_DIR, ocp)
    os.makedirs(d, exist_ok=True)
    body = json.dumps({"ocp": ocp, "arch": arch, "channels": chans,
                       "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
                      separators=(",", ":"))
    with open(os.path.join(d, "releases.js"), "w", encoding="utf-8") as f:
        f.write(f"window.OCM&&window.OCM.loadReleases({body});\n")
    print(f"  -> data/{ocp}/releases.js")


# ---------------------------------------------------------------- RHOAI additional images
RHOAI_REPO = "red-hat-data-services/rhoai-disconnected-install-helper"
RHOAI_MD = re.compile(r"^rhoai-(\d+\.\d+(?:\.\d+)?(?:-ea\.\d+)?)\.md$")


def _get(url, accept="application/json"):
    h = {"Accept": accept, "User-Agent": "ocm-picker"}
    if os.environ.get("GITHUB_TOKEN"):
        h["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r:
        return r.read().decode("utf-8", "replace")


def parse_rhoai_md(text):
    """'# Additional images:' 목록과 ImageSetConfiguration 예시의 rhods-operator 채널/버전."""
    imgs, sec = [], False
    for line in text.splitlines():
        if line.startswith("#"):
            sec = line.lower().startswith("# additional images")
            continue
        m = re.match(r"^\s*-\s+(?:name:\s*)?(\S+[@:]\S+)\s*$", line)
        if sec and m:
            imgs.append(m.group(1))
    out = {"img": list(dict.fromkeys(imgs))}
    m = re.search(r"-\s*name:\s*rhods-operator\s*\n\s*channels:\s*\n\s*-\s*name:\s*(\S+)(?:\s*\n\s*minVersion:\s*(\S+))?(?:\s*\n\s*maxVersion:\s*(\S+))?", text)
    if m:
        out.update({k: v for k, v in (("ch", m.group(1)), ("min", m.group(2)), ("max", m.group(3))) if v})
    return out


def write_rhoai(min_ver):
    files = json.loads(_get(f"https://api.github.com/repos/{RHOAI_REPO}/contents/"))
    vers = sorted((m.group(1) for f in files if (m := RHOAI_MD.match(f["name"]))), key=_vkey)
    vers = [v for v in vers if _vkey(v) >= _vkey(min_ver)]
    data = {}
    for v in vers:
        try:
            r = parse_rhoai_md(_get(f"https://raw.githubusercontent.com/{RHOAI_REPO}/main/rhoai-{v}.md", "text/plain"))
        except Exception as e:
            print(f"  [WARN] rhoai-{v}.md: {e}", file=sys.stderr)
            continue
        if r["img"]:
            data[v] = r
            print(f"  RHOAI {v}: {len(r['img'])} images" + (f", {r['ch']}" if r.get("ch") else ""))
    if not data:
        print("  [WARN] RHOAI 이미지 정보를 가져오지 못함", file=sys.stderr)
        return
    body = json.dumps({"repo": RHOAI_REPO, "versions": data,
                       "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")},
                      separators=(",", ":"))
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "rhoai.js"), "w", encoding="utf-8") as f:
        f.write(f"window.OCM&&window.OCM.loadRhoai({body});\n")
    print(f"  -> data/rhoai.js  ({len(data)} versions)")


def write_index():
    entries, releases = [], []
    if os.path.isdir(DATA_DIR):
        for ocp in os.listdir(DATA_DIR):
            vd = os.path.join(DATA_DIR, ocp)
            if not os.path.isdir(vd):
                continue
            if os.path.isfile(os.path.join(vd, "releases.js")):
                releases.append(ocp)
            for fn in os.listdir(vd):
                if fn.endswith(".meta.json"):
                    with open(os.path.join(vd, fn), encoding="utf-8") as f:
                        entries.append(json.load(f))
    order = list(CATALOG_LABELS)
    entries.sort(key=lambda m: (_vkey(m["ocp"]), order.index(m["catalog"]) if m["catalog"] in order else 99))
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(os.path.join(DATA_DIR, "index.js"), "w", encoding="utf-8") as f:
        f.write("window.OCM_INDEX = " + json.dumps(entries, ensure_ascii=False, indent=1) + ";\n")
        f.write("window.OCM_RELEASES = " + json.dumps(sorted(releases, key=_vkey)) + ";\n")
    print(f"  -> data/index.js  ({len(entries)} catalogs, releases: {', '.join(sorted(releases, key=_vkey)) or '-'})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("fbc", "out"):
        s = sub.add_parser(cmd)
        s.add_argument("--ocp", required=True, help="예: 4.22")
        s.add_argument("--catalog", required=True, help="redhat | certified | community | 기타 키")
        s.add_argument("--image", required=True, help="카탈로그 이미지 (ImageSetConfiguration 에 그대로 사용)")
        s.add_argument("--src", required=True, help="fbc: /configs 추출 디렉터리, out: list 결과 파일")
        s.add_argument("--digest", default="", help="카탈로그 이미지 digest (선택)")
        s.add_argument("--created", default="", help="카탈로그 이미지 생성 시각 (선택)")
    s = sub.add_parser("releases")
    s.add_argument("--ocp", required=True, help="예: 4.22")
    s.add_argument("--arch", default="amd64", help="amd64 | arm64 | ppc64le | s390x | multi")
    s = sub.add_parser("rhoai")
    s.add_argument("--min", default="2.25", help="수집할 최소 RHOAI 버전 (기본 2.25)")
    sub.add_parser("index")
    a = ap.parse_args()

    if a.cmd in ("fbc", "out"):
        ocp = a.ocp.lstrip("v")
        print(f"[{ocp} / {a.catalog}] {a.src}")
        extra = {k: v for k, v in (("digest", a.digest), ("created", a.created)) if v}
        if a.cmd == "fbc":
            pk, nb = build_from_fbc(a.src)
            extra["bundles"] = nb
            write_catalog(ocp, a.catalog, a.image, pk, "fbc", extra)
        else:
            write_catalog(ocp, a.catalog, a.image, build_from_out(a.src), "oc-mirror-list", extra)
    elif a.cmd == "releases":
        ocp = a.ocp.lstrip("v")
        print(f"[{ocp} / releases ({a.arch})]")
        write_releases(ocp, a.arch)
    elif a.cmd == "rhoai":
        print(f"[RHOAI additional images >= {a.min}] github.com/{RHOAI_REPO}")
        write_rhoai(a.min)
    write_index()


if __name__ == "__main__":
    main()
