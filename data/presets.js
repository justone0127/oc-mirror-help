// 기능별 오퍼레이터 묶음(프리셋)과 OLM 에 선언되지 않은 운영상 의존성.
// 이 파일은 손으로 편집합니다. 코드 수정 없이 항목을 추가/변경할 수 있습니다 (README '프리셋 편집' 참고).
//
// 프리셋 항목:
//   n     패키지 이름 (필수)
//   c     카탈로그 키 (생략하면 redhat → certified → community 순서로 찾음)
//   ch    기본으로 고를 채널 (생략하면 default 채널, 창에서 변경 가능)
//   off   true 면 기본 체크 해제 (선택 사항)
//   note  설명
// 그룹의 pick: 'one' 이면 "하나 선택" 안내만 표시 (강제하지 않음)
// images: additionalImages 후보 { ref, note, off }
// rhoai: true 면 RHOAI 버전별 노트북/런타임 이미지 선택 영역 표시 (data/rhoai.js)
window.OCM_PRESETS = [
  {
    id: 'rhoai3',
    name: 'Red Hat OpenShift AI 3.x',
    desc: 'RHOAI 3.x 설치와 주요 기능(GPU, 분산 학습, llm-d 모델 서빙, 관측성)에 필요한 오퍼레이터',
    links: [
      { t: 'RHOAI disconnected install helper', u: 'https://github.com/red-hat-data-services/rhoai-disconnected-install-helper' },
      { t: 'RHOAI 문서', u: 'https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/' },
    ],
    groups: [
      { name: '코어', items: [
        { n: 'rhods-operator', note: 'Red Hat OpenShift AI' },
      ] },
      { name: 'GPU 가속', items: [
        { n: 'nfd', note: 'GPU 노드 라벨링 (GPU Operator 사전 조건)' },
        { n: 'gpu-operator-certified', c: 'certified', note: 'NVIDIA GPU Operator' },
      ] },
      { name: '분산 워크로드 / 학습', items: [
        { n: 'kueue-operator', note: 'Red Hat build of Kueue - 작업 큐/쿼터' },
        { n: 'job-set', note: 'JobSet - Training Operator(Trainer v2)' },
        { n: 'openshift-cert-manager-operator', note: 'Kueue 등 webhook 인증서 (Kueue 사전 조건)' },
      ] },
      { name: '모델 서빙 (KServe / llm-d)', items: [
        { n: 'leader-worker-set', note: 'LWS - llm-d 멀티 노드 추론' },
        { n: 'rhcl-operator', note: 'Red Hat Connectivity Link - 인증/Rate limit (Authorino·Limitador·DNS 를 OLM 의존성으로 설치)' },
        { n: 'authorino-operator', note: 'RHCL 의존성' },
        { n: 'limitador-operator', note: 'RHCL 의존성' },
        { n: 'dns-operator', note: 'RHCL 의존성 (DNS Operator)' },
        { n: 'metallb-operator', note: '베어메탈 LoadBalancer (Gateway 외부 노출)' },
      ] },
      { name: '파이프라인', items: [
        { n: 'openshift-pipelines-operator-rh', note: 'Red Hat OpenShift Pipelines' },
      ] },
      { name: '관측성', items: [
        { n: 'cluster-observability-operator', note: 'Cluster Observability Operator' },
        { n: 'opentelemetry-product', note: 'Red Hat build of OpenTelemetry' },
        { n: 'tempo-product', note: 'Tempo (분산 트레이싱)' },
      ] },
    ],
    images: [
      { ref: 'registry.redhat.io/rhel9/postgresql-16:latest', note: 'MaaS / Llama Stack / Model Registry (PostgreSQL)', off: true },
      { ref: 'registry.redhat.io/rhel9/mysql-80:latest', note: 'Model Registry / TrustyAI (MySQL)', off: true },
    ],
    rhoai: true,
  },
  {
    id: 'virt',
    name: 'OpenShift Virtualization',
    desc: '가상 머신 실행·마이그레이션. 스토리지는 환경에 맞게 선택 (SNO: LVM Storage 또는 Local Storage)',
    links: [
      { t: 'OpenShift Virtualization 문서', u: 'https://docs.redhat.com/en/documentation/openshift_container_platform/latest/html/virtualization/' },
    ],
    groups: [
      { name: '코어', items: [
        { n: 'kubevirt-hyperconverged', note: 'OpenShift Virtualization' },
      ] },
      { name: '마이그레이션', items: [
        { n: 'mtv-operator', note: 'Migration Toolkit for Virtualization (VMware 등 → OpenShift)' },
      ] },
      { name: '스토리지 (환경에 맞게 선택)', pick: 'one', items: [
        { n: 'lvms-operator', note: 'LVM Storage - SNO / 소규모 (RWO)', off: true },
        { n: 'local-storage-operator', note: 'Local Storage - 로컬 디스크 PV', off: true },
        { n: 'odf-operator', note: 'OpenShift Data Foundation - RWX 블록 (라이브 마이그레이션)', off: true },
      ] },
      { name: '네트워크 / 가용성 (선택)', items: [
        { n: 'kubernetes-nmstate-operator', note: 'NMState - VM 용 브리지/VLAN 구성', off: true },
        { n: 'node-healthcheck-operator', note: '노드 장애 감지', off: true },
        { n: 'self-node-remediation', note: '장애 노드 자동 복구 (Node Health Check 와 함께)', off: true },
      ] },
    ],
    notes: '고객사 스토리지 벤더의 CSI 드라이버 오퍼레이터는 Certified 카탈로그에서 검색해 추가하세요.',
  },
  {
    id: 'ossm3',
    name: 'Service Mesh 3.x',
    desc: 'Red Hat OpenShift Service Mesh 3 + Kiali + 분산 트레이싱',
    links: [
      { t: 'Service Mesh 3 문서', u: 'https://docs.redhat.com/en/documentation/red_hat_openshift_service_mesh/' },
    ],
    groups: [
      { name: '코어', items: [
        { n: 'servicemeshoperator3', note: 'Red Hat OpenShift Service Mesh 3' },
        { n: 'kiali-ossm', note: 'Kiali (콘솔/시각화)' },
      ] },
      { name: '트레이싱 / 인증서', items: [
        { n: 'opentelemetry-product', note: 'Red Hat build of OpenTelemetry' },
        { n: 'tempo-product', note: 'Tempo' },
        { n: 'openshift-cert-manager-operator', note: 'cert-manager Operator for Red Hat OpenShift' },
      ] },
    ],
  },
  {
    id: 'opp',
    name: 'OpenShift Platform Plus (OPP)',
    desc: 'ACM · ACS · Quay · ODF',
    links: [
      { t: 'ACM 문서', u: 'https://docs.redhat.com/en/documentation/red_hat_advanced_cluster_management_for_kubernetes/' },
      { t: 'ODF 문서', u: 'https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/' },
    ],
    groups: [
      { name: '멀티 클러스터 관리', items: [
        { n: 'advanced-cluster-management', note: 'Advanced Cluster Management for Kubernetes' },
        { n: 'multicluster-engine', note: 'multicluster engine (ACM 이 자동 설치)' },
      ] },
      { name: '보안', items: [
        { n: 'rhacs-operator', note: 'Advanced Cluster Security for Kubernetes' },
      ] },
      { name: '레지스트리', items: [
        { n: 'quay-operator', note: 'Red Hat Quay' },
      ] },
      { name: '스토리지 (ODF)', items: [
        { n: 'odf-operator', note: 'OpenShift Data Foundation (설치 시 odf-dependencies 구독 생성)' },
        { n: 'odf-dependencies', note: 'Data Foundation Dependencies (ceph-csi, rook, ocs, mcg 등을 OLM 의존성으로 설치)' },
        { n: 'odf-csi-addons-operator', note: 'CSI Addons' },
        { n: 'odf-external-snapshotter-operator', note: 'Snapshot Controller' },
        { n: 'odf-prometheus-operator', note: 'Prometheus Operator (ODF 용)' },
        { n: 'odf-multicluster-orchestrator', note: 'DF Multicluster Orchestrator - Regional/Metro DR 사용 시', off: true },
      ] },
    ],
  },
];

// OLM 에 선언되지 않았지만 운영상 함께 미러링해야 하는 오퍼레이터
// (오퍼레이터가 설치 중 다른 오퍼레이터의 Subscription 을 직접 만들거나, 문서상 사전 조건인 경우)
window.OCM_SOFT_DEPS = {
  'advanced-cluster-management': [{ n: 'multicluster-engine', why: 'ACM 이 MCE 를 자동 설치' }],
  'odf-operator': [{ n: 'odf-dependencies', why: 'odf-operator 가 odf-dependencies 구독을 생성' }],
  'gpu-operator-certified': [{ n: 'nfd', why: 'GPU 노드 라벨링 (사전 조건)' }],
  'kueue-operator': [{ n: 'openshift-cert-manager-operator', why: 'Kueue 사전 조건' }],
  'mtv-operator': [{ n: 'kubevirt-hyperconverged', why: 'VM 마이그레이션 대상' }],
  'kiali-ossm': [{ n: 'servicemeshoperator3', why: '메시 시각화 대상' }],
};
