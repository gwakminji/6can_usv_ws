"""gui_main_node의 웹 대시보드 HTML/JS.

Dongwon님이 만든 캔버스 게임 스타일 GUI(usv_gui 레포)를 이 프로젝트의 인터페이스 계약에 맞게
이식한 버전이다. 원본은 roslibjs로 rosbridge_websocket에 직접 붙는 구조라서 데이터 가져오는 부분만
전부 폴링 방식으로 바꿨다 (게임 로직 자체는 그대로).

이미지 에셋(배/물고기/쓰레기 스프라이트 등)은 gui_main_node.py가 web/ 디렉터리를
static_folder로 서빙해서 "lake.png" 같은 상대 경로가 그대로 동작한다.
"""

INDEX_HTML = """<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<title>USV GCS Dashboard</title>
<style>
  body {
      margin: 0; padding: 0; background-color: #1a1a1a; color: #fff;
      display: flex; justify-content: center; align-items: center; height: 100vh;
      font-family: '맑은 고딕', sans-serif; overflow: hidden;
  }
  #gameContainer { position: relative; display: inline-block; transform-origin: center center; }
  canvas { border: 3px solid #e29578; background-color: #2c1a11; box-shadow: 0 0 20px rgba(0,0,0,0.8); }

  #gpsBanner {
      position: absolute; top: 0; left: 0; right: 0; z-index: 20;
      background: #522; color: #fdd; padding: 6px; text-align: center; font-size: 12px;
      display: none;
  }

  #cameraPanel {
      /* 왼쪽 열(미니맵)과 가로폭을 맞추고, 그 아래 남는 공간을 캔버스
         하단(600px)까지 꽉 채운다. 펌프제어 패널은 우측 사이드바로 옮겨서 이 열엔
         미니맵만 남았다. */
      position: absolute; top: 185px; left: 18px; width: 130px; height: 415px;
      background-color: #1c100a; border: 2px solid #38bdf8; box-sizing: border-box;
      padding: 3px; display: flex; flex-direction: column; gap: 6px;
      z-index: 10;
  }
  .cam-box {
      width: 100%; flex: 1; min-height: 0; background-color: #000; border: 1px solid #38bdf8;
      position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center;
  }
  .cam-title {
      position: absolute; top: 2px; left: 4px; font-size: 10px; color: #38bdf8; font-weight: bold;
      background: rgba(0, 0, 0, 0.7); padding: 1px 3px; border-radius: 2px; z-index: 2;
  }
  .cam-box img { width: 100%; height: 100%; object-fit: cover; }
  .cam-warn { font-size: 9px; color: #fdd; text-align: center; padding: 0 4px; }

  #actuatorPanel {
      /* 우측 사이드바(수질 센서 모니터링 패널 바로 아래, 뽑기 패널 바로 위)에 들어간다.
         그 두 패널과 가로폭(200px)을 맞추고, sidebarX를 따라가야 해서 left는
         updateResponsiveCanvas()가 매 프레임 갱신한다. */
      position: absolute; top: 248px; left: 585px; width: 200px; box-sizing: border-box;
      background-color: #150d08; border: 2px solid #e29578; padding: 6px; font-size: 11px;
      z-index: 10;
  }
  #actuatorPanel .title {
      display: inline-block; vertical-align: middle;
      color: #ffd166; font-weight: bold; margin-bottom: 4px;
  }
  .gamepad-btn-badge {
      display: inline-flex; align-items: center; justify-content: center;
      width: 15px; height: 15px; border-radius: 50%; background: #e6423f;
      color: #fff; font-size: 9px; font-weight: bold; font-family: Arial, sans-serif;
      vertical-align: middle; margin-right: 5px; box-shadow: inset 0 0 2px rgba(0,0,0,0.5);
  }
  .gamepad-btn-badge.badge-green { background: #3ddc55; }
  .pump-fire-hint {
      display: flex; align-items: center; gap: 5px;
      margin-top: 6px; font-size: 11px; font-weight: bold; color: #ffd166;
  }
  .pump-fire-hint .gamepad-btn-badge { margin-right: 0; }
  #actuatorPanel button {
      background: #246; color: #fff; border: none; border-radius: 4px; padding: 4px 8px;
      cursor: pointer; margin-right: 4px; font-size: 10px;
  }
  #actuatorPanel button:hover { background: #357; }
  #actuatorPanel input[type=color] { width: 32px; height: 22px; vertical-align: middle; }
  .pump-mode-bar { display: flex; gap: 4px; margin-bottom: 6px; }
  .pump-mode-box {
      flex: 1; display: flex; flex-direction: column; align-items: center; gap: 3px;
      background: #1c100a; border: 1px solid #444; border-radius: 4px; padding: 5px 0;
  }
  .pump-mode-light {
      width: 10px; height: 10px; border-radius: 50%; background: #555;
      box-shadow: inset 0 0 2px rgba(0,0,0,0.8);
  }
  .pump-mode-box.on .pump-mode-light { background: #3ddc55; box-shadow: 0 0 6px 2px rgba(61,220,85,0.8); }
  .pump-mode-label { font-size: 9px; color: #ccc; }

  .panel-hidden { display: none !important; }
</style>
</head>
<body>
<div id="gameContainer">
    <div id="gpsBanner">⚠ GPS 신호 없음 (마지막 위치 유지 중)</div>
    <canvas id="gameCanvas" width="800" height="600"></canvas>

    <div id="cameraPanel" class="panel-hidden">
        <div class="cam-box">
            <span class="cam-title">📷 수면 (Surface)</span>
            <img id="surfaceCam" alt="수면 카메라 연결 중..." onerror="this.style.opacity=0.3">
        </div>
        <div class="cam-box">
            <span class="cam-title">🌊 수중 (Underwater)</span>
            <img id="underwaterCam" alt="수중 카메라 연결 중..." onerror="this.style.opacity=0.3">
        </div>
    </div>

    <div id="actuatorPanel" class="panel-hidden">
        <span class="gamepad-btn-badge">B</span><div class="title">펌프 제어</div>
        <div class="pump-mode-bar">
            <div class="pump-mode-box" id="pumpModeAutoBox">
                <span class="pump-mode-light"></span>
                <span class="pump-mode-label">자동</span>
            </div>
            <div class="pump-mode-box" id="pumpModeManualBox">
                <span class="pump-mode-light"></span>
                <span class="pump-mode-label">수동</span>
            </div>
        </div>
        <div class="pump-fire-hint"><span class="gamepad-btn-badge badge-green">A</span>펌프 작동</div>
    </div>
</div>

<script>
// --- [카메라 스트림 표시 여부] 웹 대시보드에서 카메라 화면을 쓰지 않기로 해서 껐다.
// 다시 켜려면 이 값만 true로 바꾸면 된다 (아래 카메라 관련 코드는 그대로 둬도 됨 -
// 이 플래그가 스트림 연결/패널 표시를 전부 막는다). README "카메라 표시 켜기/끄기" 참고.
const SHOW_CAMERA = false;

// --- [카메라 스트림] B1 보드의 camera_streaming 패키지(http_video_server)가 MJPEG를
// 직접 서빙한다 - GCS 자신이 아니라 B1 보드 위에서 도는 서버라 GCS의 location.hostname으로
// 폴백하면 안 된다(폴백하면 GCS 자신의 8000번을 찍어서 조용히 검은 화면이 된다). 포트는
// camera_streaming 쪽 고정값(8000). 호스트는 gui_main_node.py의 camera_host 파라미터
// (gcs.launch.py camera_host 인자 또는 config/gcs_params.yaml)로 주입된다. 값이 비어있으면
// 폴백 없이 화면에 설정 안내를 띄운다 - 잘못된 주소로 붙는 것보다 낫다.
const CAMERA_PORT = 8000;
const cameraHost = "__CAMERA_HOST__";
if (SHOW_CAMERA && cameraHost) {
    document.getElementById('surfaceCam').src =
        `http://${cameraHost}:${CAMERA_PORT}/stream?topic=/camera/surface/image_raw`;
    document.getElementById('underwaterCam').src =
        `http://${cameraHost}:${CAMERA_PORT}/stream?topic=/camera/underwater/image_raw`;
} else if (SHOW_CAMERA) {
    document.querySelectorAll('#cameraPanel .cam-box').forEach((box) => {
        const warn = document.createElement('div');
        warn.className = 'cam-warn';
        warn.textContent = 'camera_host 미설정 (gcs_params.yaml)';
        box.appendChild(warn);
    });
}

// --- [펌프] 조종은 조이스틱 하나로만 하므로 펌프도 joy_to_cmd_node가 조이스틱 버튼으로
// 직접 /actuator/pump_cmd를 발행한다. 이 화면은 그 상태를 표시만 한다(버튼 없음). ---

// --- [자동 제어] 펌프와 마찬가지로 joy_to_cmd_node가 조이스틱 버튼으로 직접
// /actuator/auto_mode를 발행한다. 이 화면은 그 상태를 표시만 한다(버튼 없음). ---

// --- [GPS] 위경도를 캔버스 픽셀 좌표로 변환 ---
// 📍 송도 센트럴파크 기준 위경도 범위 설정 - GPS 수신 전 기본 위치(및 미니맵)가
// 실제로 존재하는 장소를 가리키도록 여기 좌표로 잡았다.
const gpsBounds = {
    minLat: 37.3888,
    maxLat: 37.3908,
    minLng: 126.6380,
    maxLng: 126.6400
};

function convertGpsToPixel(lat, lng) {
    let x = ((lng - gpsBounds.minLng) / (gpsBounds.maxLng - gpsBounds.minLng)) * mapWidth;
    let y = (1.0 - (lat - gpsBounds.minLat) / (gpsBounds.maxLat - gpsBounds.minLat)) * mapHeight;

    return {
        x: Math.max(30, Math.min(mapWidth - 30, x)),
        y: Math.max(30, Math.min(mapHeight - 30, y))
    };
}

let isGpsReceived = false;

// --- [미니맵] 구글 정적맵 위성 사진 위에 실제 GPS 좌표를 표시 ---
// TODO: 구글 맵 Static API 키 채워넣기. 저장소가 public이라 여기 직접 커밋하지 말 것
// (팀 키 사용 여부/도메인 제한 확인 후 배포 환경에서만 주입 권장).
const googleApiKey = "";
const miniMapImg = new Image();
let currentLat = (gpsBounds.minLat + gpsBounds.maxLat) / 2;
let currentLng = (gpsBounds.minLng + gpsBounds.maxLng) / 2;

function updateMiniMapUrl(lat, lng) {
    currentLat = lat ?? currentLat;
    currentLng = lng ?? currentLng;
    miniMapImg.src = `https://maps.googleapis.com/maps/api/staticmap?center=${currentLat},${currentLng}&zoom=17&size=130x137&maptype=satellite&key=${googleApiKey}`;

    miniMapImg.onerror = function() {
        console.error("❌ 구글맵 이미지 로드 실패! API 키, 결제 카드 등록 여부 또는 Static Maps API 활성화를 확인하세요.");
    };
}

updateMiniMapUrl(currentLat, currentLng);

// 조종은 조이스틱(joy_to_cmd_node)이 하고, 이 화면은 그 결과를 보여주기만 한다.
let lastCmdVel = { linearX: 0, angularZ: 0 };

// /water_quality/data의 실제 JSON 스키마 (water_quality_node.py 기준) 그대로 보관
let sensorWQ = {
    temp_c: null, ph: null, do_mg_l: null,
    turbidity_voltage_v: null, clarity_pct: null, clarity_level: null
};

// /battery/status의 실제 JSON 스키마: thruster1/thruster2/pump_ctrl/sensor_board 각각 {current_a, percentage}
let batteryStatus = null;
let batteryWarningPct = 20;

// --- [상태 폴링] gui_main_node.py의 /api/state를 1초 간격으로 읽어온다 ---
async function refreshState() {
    try {
        const res = await fetch('/api/state');
        const s = await res.json();

        const banner = document.getElementById('gpsBanner');
        banner.style.display = (s.gps_has_fix === false) ? 'block' : 'none';

        if (s.gps_fix) {
            let pos = convertGpsToPixel(s.gps_fix.latitude, s.gps_fix.longitude);
            targetX = pos.x;
            targetY = pos.y;
            updateMiniMapUrl(s.gps_fix.latitude, s.gps_fix.longitude);
            if (!isGpsReceived) {
                isGpsReceived = true;
                console.log("🛰️ 첫 GPS 좌표 수신 완료!");
            }
        }

        if (s.cmd_vel) {
            lastCmdVel.linearX = s.cmd_vel.linear_x;
            lastCmdVel.angularZ = s.cmd_vel.angular_z;
        }

        if (s.pump_on !== null && s.pump_on !== undefined) {
            isPumping = s.pump_on;
        }

        if (s.auto_mode !== null && s.auto_mode !== undefined) {
            // 펌프는 기본적으로 수질에 따라 자동 작동하고, B 버튼으로 자동/수동을 토글,
            // A 버튼으로 수동 모드일 때 직접 구동한다(actuator_driver_node.py). 배 조종
            // 스틱(cmd_vel)은 펌프 모드와 무관하니 여기서 보지 않는다 - /actuator/auto_mode
            // 값만 그대로 반영한다.
            document.getElementById('pumpModeAutoBox').classList.toggle('on', s.auto_mode === true);
            document.getElementById('pumpModeManualBox').classList.toggle('on', s.auto_mode === false);
        }

        if (s.water_quality) {
            sensorWQ = s.water_quality;
        }

        batteryStatus = s.battery_status;
        if (s.battery_warning_pct !== undefined) batteryWarningPct = s.battery_warning_pct;
    } catch (e) {
        console.error(e);
    }
}
setInterval(refreshState, 1000);
refreshState();
// -----------------------

const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");

// 📂 이미지 자원 관리 객체 (오로라 green, yellow, red 추가)
const assets = {
    lake: new Image(),
    ending: new Image(),
    mainstart: new Image(),
    fourFish: new Image(),
    pixelFishes: new Image(),
    ship: new Image(),
    garbage1: new Image(),
    garbage2: new Image(),
    garbageSmall1: new Image(),
    garbageSmall2: new Image(),
    garbageSmall3: new Image(),
    waterArrow: new Image(),
    green: new Image(),
    yellow: new Image(),
    red: new Image(),
    logoFacillity: new Image(),
    logoInu: new Image(),
    logoYouth: new Image()
};

// 이미지 파일명 매칭 설정
assets.lake.src = "lake.png";
assets.ending.src = "ending.png";
assets.mainstart.src = "mainstart.png";
assets.fourFish.src = "4fish.png";
assets.pixelFishes.src = "PixelFishes.png";
assets.ship.src = "ship.jpg";
assets.garbage1.src = "garbage bag 1.png";
assets.garbage2.src = "garbage bag 2.png";
assets.garbageSmall1.src = "garbage bag small 1.png";
assets.garbageSmall2.src = "garbage bag small 2.png";
assets.garbageSmall3.src = "garbage bag small 3.png";
assets.waterArrow.src = "Water Arrow Preview.gif";
assets.green.src = "green.png";
assets.yellow.src = "yellow.png";
assets.red.src = "red.png";
assets.logoFacillity.src = "logo_facillity.png";
assets.logoInu.src = "logo_inu.png";
assets.logoYouth.src = "logo_youth.png";

// 시작/엔딩 화면 우측 하단에 로고 3개를 원본 비율 유지한 채 가로로 나열해서 그린다.
function drawCornerLogos(bottomY, rightMargin = 15) {
    // 로고마다 원본 가로세로 비율이 달라서 카드 크기가 제각각이면 어중간해 보이므로,
    // 흰 배경판의 폭(commonW)을 통일한다 - 세 로고 다 이 폭에 맞춰 자기 비율대로
    // 높이만 알아서 정해진다. 카드 사이 간격(gap)도 최대한 좁힌다.
    const commonW = 150;
    const pad = 6;
    const gap = 2;
    // 인천대(logoInu)는 원본 비율상 세로가 유독 길어져서 카드 폭은 통일하되
    // 로고 자체는 scale만큼 작게 그려서(카드 안에서 가운데 정렬) 세로 크기를 줄인다.
    const items = [
        { img: assets.logoFacillity, scale: 1 },
        { img: assets.logoInu, scale: 0.75 },
        { img: assets.logoYouth, scale: 1 }
    ].map(({ img, scale }) => {
        const ratio = (img.complete && img.naturalWidth && img.naturalHeight)
            ? img.naturalWidth / img.naturalHeight
            : 0;
        const w = commonW * scale;
        return { img, w, h: ratio ? w / ratio : 0 };
    });
    const plateW = commonW + pad * 2;
    const totalH = items.reduce((sum, it) => sum + (it.h > 0 ? it.h + pad * 2 : 0), 0)
        + gap * (items.length - 1);
    const x = 800 - rightMargin - plateW;
    let y = bottomY - totalH;
    items.forEach(({ img, w, h }) => {
        if (h <= 0) return;
        const cardH = h + pad * 2;
        ctx.fillStyle = "rgba(255,255,255,0.85)";
        ctx.fillRect(x, y, plateW, cardH);
        ctx.strokeStyle = "rgba(0,0,0,0.2)";
        ctx.lineWidth = 1;
        ctx.strokeRect(x, y, plateW, cardH);
        ctx.drawImage(img, x + pad + (commonW - w) / 2, y + pad, w, h);
        y += cardH + gap;
    });
}

// 🎵 오디오 관리
const bgm = {
    main: new Audio("bgm_main.mp3"),
    game: new Audio("bgm_game.mp3"),
    ending: new Audio("bgm_ending.mp3")
};
Object.values(bgm).forEach(b => { b.loop = true; });
bgm.main.volume = 0.5;
bgm.ending.volume = 0.5;
bgm.game.volume = 0.15;

const sfx = {
    coin: new Audio("sfx_coin.wav"),
    gacha: new Audio("sfx_gacha.wav"),
    nogold: new Audio("sfx_nogold.wav"),
    trash: new Audio("sfx_trash.wav"),
    pump: new Audio("sfx_pump.wav")
};
sfx.pump.loop = true;  // 펌프는 누르는 동안 계속 반복
Object.values(sfx).forEach(s => { s.volume = 0.7; });

let currentBgm = null;
function playBgm(key) {
    if (currentBgm) { currentBgm.pause(); currentBgm.currentTime = 0; }
    currentBgm = bgm[key];
    currentBgm.play().catch(() => {});
}
function playSfx(key) {
    sfx[key].currentTime = 0;
    sfx[key].play().catch(() => {});
}

// 🎵 오디오 관리
const bgm = {
    main: new Audio("bgm_main.mp3"),
    game: new Audio("bgm_game.mp3"),
    ending: new Audio("bgm_ending.mp3")
};
Object.values(bgm).forEach(b => { b.loop = true; b.volume = 0.5; });

const sfx = {
    coin: new Audio("sfx_coin.wav"),
    gacha: new Audio("sfx_gacha.wav"),
    nogold: new Audio("sfx_nogold.wav"),
    trash: new Audio("sfx_trash.wav"),
    pump: new Audio("sfx_pump.wav")
};
sfx.pump.loop = true;  // 펌프는 누르는 동안 계속 반복
Object.values(sfx).forEach(s => { s.volume = 0.7; });

let currentBgm = null;
function playBgm(key) {
    if (currentBgm) { currentBgm.pause(); currentBgm.currentTime = 0; }
    currentBgm = bgm[key];
    currentBgm.play().catch(() => {});
}
function playSfx(key) {
    sfx[key].currentTime = 0;
    sfx[key].play().catch(() => {});
}

// 게임 상태 관리 ("main" 또는 "game" 또는 "ending")
let gameState = "main";

// 게임 변수들
let initialTime = 60;  // 게임 시간 90초 -> 60초 변경
let timeLeft = initialTime;
let targetScore = 10000;
let isGameOver = false;
let cheatClickCount = 0;
let waterQuality = 70.0;
let maxWaterQuality = 100.0;
let gold = 300;
let score = 0;
let fishCount = 4;
let ownedSpecialFishes = { witch: 0, ghost: 0, santa: 0, pumpkin: 0 };
let ghostGoldTimer = 0;

// 초광폭 화면에서 호수 뷰포트가 원래 맵 폭(1140)보다 넓어지면 배경 이미지가 다 못 채워서
// 빈 공간이 생기므로, updateResponsiveCanvas()가 뷰포트 폭에 맞춰 이 값을 같이 늘려준다.
// 최소값 1140은 기존 디자인 크기 - 좁은 화면에서는 그 아래로 줄어들지 않는다.
let mapWidth = 1140;
const mapHeight = 1200;

// 디폴트 위치 설정 (GPS 수신 전에는 중앙에 위치)
let targetX = mapWidth / 2;
let targetY = mapHeight / 2;

let boatAngle = 0.0;
let boatSpriteIndex = 0; // 스프라이트 프레임 번호 직접 지정
let isPumping = false; // 조이스틱 버튼 -> /actuator/pump_cmd -> refreshState() 폴링으로 갱신됨

let fishes = [];
let monsters = [];
let monsterSpawnTimer = 0;
let activeCardShown = false;
let activeCardKey = null;
let cardHideTimer = null;
let notificationText = "";
let notificationTimer = null;

// 뽑기 등급표: chance는 100 기준 당첨 확률(%) - 점수(score_val)가 높은 물고기일수록
// 낮게 잡아서 좋은 물고기일수록 잘 안 나오게 한다. 4개 합은 100이어야 함.
const specialFishTemplates = {
    witch: { name: "WITCH FISH", kor_name: "마녀 피쉬", rarity: "레어", chance: 55, score_val: 15, desc: "쓰레기 패널티 30% 완화 🎩" },
    ghost: { name: "GHOST LOBSTER", kor_name: "유령 가재", rarity: "에픽", chance: 28, score_val: 25, desc: "10초마다 +15G 생산 👻" },
    santa: { name: "SANTA GOLDFISH", kor_name: "산타 금붕어", rarity: "유니크", chance: 13, score_val: 35, desc: "적정 수질 시 점수 1.4배 🎅" },
    pumpkin: { name: "PUMPKIN FISH", kor_name: "호박 왕관피쉬", rarity: "레전더리", chance: 4, score_val: 50, desc: "초당 기본 점수 든든하게 +50점 👑" }
};
const GACHA_COST = 150;

function formatElapsedTime(sec) {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

const RESULT_FISH_SPECIES = [
    { key: "witch", icon: "🎩" },
    { key: "ghost", icon: "👻" },
    { key: "santa", icon: "🎅" },
    { key: "pumpkin", icon: "👑" }
].map(sp => ({ ...sp, label: specialFishTemplates[sp.key].kor_name }));

// 이번 판 결과(최종점수/소요시간/수집 물고기 총합 + 종류별 수집 수)를 카드 하나에 꽉 채워 보여준다.
// 여러 판 기록을 남기는 랭킹판이 아니라 방금 끝난 게임 하나의 결과만 보여준다.
function drawResultPanel(panelX, panelY, panelW, panelH) {
    const grad = ctx.createLinearGradient(panelX, panelY, panelX, panelY + panelH);
    grad.addColorStop(0, "#1b2f5c");
    grad.addColorStop(1, "#0a1730");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.roundRect(panelX, panelY, panelW, panelH, 20);
    ctx.fill();
    ctx.strokeStyle = "#3aa7ff";
    ctx.lineWidth = 2;
    ctx.stroke();

    const cx = panelX + panelW / 2;
    ctx.textAlign = "center";

    let y = panelY + 32;
    ctx.fillStyle = "#ffd166";
    ctx.font = "bold 18px '맑은 고딕'";
    ctx.fillText(`🏆 최종 점수 : ${score.toLocaleString()}점`, cx, y);

    y += 26;
    ctx.fillStyle = "#8fd6ff";
    ctx.font = "bold 14px '맑은 고딕'";
    ctx.fillText(`⏱️ 소요 시간 : ${formatElapsedTime(initialTime - timeLeft)}`, cx, y);

    const totalFish = Object.values(ownedSpecialFishes).reduce((a, b) => a + b, 0);
    y += 24;
    ctx.fillStyle = "#c9f7c0";
    ctx.font = "bold 14px '맑은 고딕'";
    ctx.fillText(`🐟 수집한 물고기 : ${totalFish}마리`, cx, y);

    // 종류별 수집 수를 2x2 칸으로 나눠서 남은 공간을 꽉 채운다.
    y += 20;
    const gridW = panelW - 32, gridH = panelY + panelH - 14 - y;
    const cellW = gridW / 2, cellH = gridH / 2;
    RESULT_FISH_SPECIES.forEach(({ key, icon, label }, i) => {
        const col = i % 2, row = Math.floor(i / 2);
        const cellX = panelX + 16 + cellW * col;
        const cellY = y + cellH * row;
        ctx.fillStyle = "rgba(255,255,255,0.08)";
        ctx.fillRect(cellX + 4, cellY + 3, cellW - 8, cellH - 6);
        ctx.fillStyle = "#ffffff";
        ctx.font = "11px '맑은 고딕'";
        ctx.fillText(`${icon} ${label}`, cellX + cellW / 2, cellY + cellH / 2 - 2);
        ctx.fillStyle = "#ffd166";
        ctx.font = "bold 12px '맑은 고딕'";
        ctx.fillText(`${ownedSpecialFishes[key]}마리`, cellX + cellW / 2, cellY + cellH / 2 + 14);
    });

    ctx.textAlign = "left";
}

// 마우스 클릭 이벤트 처리
canvas.addEventListener("click", (e) => {
    const rect = canvas.getBoundingClientRect();
    // 화면 확대(fitGameContainer의 transform: scale)로 캔버스의 실제 렌더링 크기가
    // 내부 해상도(800x600)와 달라지므로, 클릭 좌표를 내부 해상도 기준으로 환산한다.
    const x = (e.clientX - rect.left) * (canvas.width / rect.width);
    const y = (e.clientY - rect.top) * (canvas.height / rect.height);

    if (gameState === "main") {
        // "[START] 버튼을 눌러 게임을 시작하세요!" 문구(400,560 중심) 자체를 클릭 영역으로 사용
        if (x >= 220 && x <= 580 && y >= 545 && y <= 575) {
            startGame();
        }
    } else if (gameState === "game") {
        if (activeCardShown) {
            hideFishCardPopup();
            return;
        }
        if (x >= 0 && x <= 40 && y >= 0 && y <= 40) {
            triggerEndingCheat();
            return;
        }
        const sidebarX = canvas.width - 230;
        if (x >= sidebarX + 25 && x <= sidebarX + 205 && y >= 380 && y <= 416) {
            rollGachaFish();
        }
    } else if (gameState === "ending") {
        // "[BACK] 메인화면" 텍스트(우측 하단, 790,585에 오른쪽 정렬로 찍힘) 자체를 클릭 영역으로 사용
        if (x >= 670 && x <= 800 && y >= 568 && y <= 592) {
            gameState = "main";
            playBgm("main");
        }
    }
});

// 메인화면 BGM - 브라우저 정책상 첫 클릭 이후에만 재생 가능
document.addEventListener("click", () => {
    if (gameState === "main" && (!currentBgm || currentBgm.paused)) {
        playBgm("main");
    }
}, { once: true });

function startGame() {
    gameState = "game";
    playBgm("game");
    timeLeft = initialTime;
    score = 0;
    gold = 300;
    waterQuality = 70.0;
    isGameOver = false;
    fishCount = 4;
    ownedSpecialFishes = { witch: 0, ghost: 0, santa: 0, pumpkin: 0 };
    targetX = mapWidth / 2;
    targetY = mapHeight / 2;
    isGpsReceived = false;
    fishes = [];
    monsters = [];
    for (let i = 0; i < fishCount; i++) spawnRandomNormalFish();
}

function spawnRandomNormalFish() {
    fishes.push({
        x: Math.random() * (mapWidth - 200) + 100,
        y: Math.random() * (mapHeight - 200) + 100,
        dir: Math.random() < 0.5 ? -1 : 1,
        type: Math.floor(Math.random() * 50),
        isSpecial: false
    });
}

function spawnSpecialFish(fishKey) {
    let indices = { witch: 1, ghost: 19, santa: 28, pumpkin: 54 };
    fishes.push({
        x: Math.random() * (mapWidth - 300) + 150,
        y: Math.random() * (mapHeight - 300) + 150,
        dir: Math.random() < 0.5 ? -1 : 1,
        type: indices[fishKey],
        isSpecial: true,
        key: fishKey,
        name: specialFishTemplates[fishKey].kor_name
    });
}

function spawnMonster() {
    let isLarge = Math.random() < 0.25; // 큰 쓰레기 25% 확률로 등장
    let chosenImg;
    if (isLarge) {
        let largeImgs = [assets.garbage1, assets.garbage2];
        chosenImg = largeImgs[Math.floor(Math.random() * largeImgs.length)];
    } else {
        let smallImgs = [assets.garbageSmall1, assets.garbageSmall2, assets.garbageSmall3];
        chosenImg = smallImgs[Math.floor(Math.random() * smallImgs.length)];
    }
    monsters.push({
        x: Math.random() * (mapWidth - 200) + 100,
        y: Math.random() * (mapHeight - 200) + 100,
        photo: chosenImg,
        hp: 3,
        isLarge: isLarge
    });
}

function showInGameMessage(text) {
    notificationText = text;
    if (notificationTimer) clearTimeout(notificationTimer);
    notificationTimer = setTimeout(() => {
        notificationText = "";
    }, 2000);
}

function showFishCardPopup(fishKey) {
    activeCardShown = true;
    activeCardKey = fishKey;
    if (cardHideTimer) clearTimeout(cardHideTimer);
    cardHideTimer = setTimeout(() => {
        hideFishCardPopup();
    }, 1500);
}

function hideFishCardPopup() {
    activeCardShown = false;
}

// 조이스틱 버튼 하나로 실행되는 랜덤 뽑기. 4개 물고기 중 하나를 chance(%) 가중치로
// 추첨한다 - 값이 좋은 물고기(pumpkin 등)일수록 chance가 낮게 설정되어 있어 잘 안 나온다.
function rollGachaFish() {
    if (gold < GACHA_COST) {
        playSfx("nogold");
        showInGameMessage(`❌ 골드가 부족합니다! (필요: ${GACHA_COST}G)`);
        return;
    }
    gold -= GACHA_COST;
    playSfx("gacha");

    const keys = Object.keys(specialFishTemplates);
    const totalChance = keys.reduce((sum, k) => sum + specialFishTemplates[k].chance, 0);
    let roll = Math.random() * totalChance;
    let fishKey = keys[keys.length - 1];
    for (const k of keys) {
        if (roll < specialFishTemplates[k].chance) { fishKey = k; break; }
        roll -= specialFishTemplates[k].chance;
    }

    let info = specialFishTemplates[fishKey];
    fishCount += 1;
    ownedSpecialFishes[fishKey] += 1;
    spawnSpecialFish(fishKey);
    showInGameMessage(`🎉 [${info.rarity}] ${info.kor_name} 획득! (-${GACHA_COST}G)`);
    showFishCardPopup(fishKey);
}

function triggerEndingCheat() {
    cheatClickCount++;
    let remaining = 5 - cheatClickCount;
    if (remaining > 0) {
        showInGameMessage(`✨ 엔딩 치트: ${remaining}번 더 누르면 엔딩!`);
    } else {
        showInGameMessage("🚀 엔딩 치트 활성화 완료!");
        score = targetScore;
        gameState = "ending";
    }
}

// 게임 루프 타이머
setInterval(() => {
    if (gameState !== "game" || isGameOver) return;

    timeLeft -= 1;
    let currentTickScore = 0;
    let pumpkinCount = ownedSpecialFishes.pumpkin;
    let pumpkinBonus = 50 * pumpkinCount;

    fishes.forEach(fish => {
        if (fish.isSpecial) {
            let val = specialFishTemplates[fish.key].score_val;
            if (fish.key === "pumpkin") val += pumpkinBonus;
            currentTickScore += val;
        } else {
            currentTickScore += 5;
        }
    });

    let santaCount = ownedSpecialFishes.santa;
    if (waterQuality >= 60.0) {
        currentTickScore = Math.floor(currentTickScore * (1.0 + santaCount * 0.4));
    }

    if (waterQuality >= 100.0) {
        currentTickScore += 30;
    }

    score += currentTickScore;

    if (score >= targetScore) {
        gameState = "ending";
        playBgm("ending");
        sfx.pump.pause(); sfx.pump.currentTime = 0;
        return;
    }

    if (timeLeft <= 0) {
        isGameOver = true;
        gameState = "ending";
        playBgm("ending");
        sfx.pump.pause(); sfx.pump.currentTime = 0;
        return;
    }

    let nearbyGarbage = monsters.filter(m => Math.hypot(targetX - m.x, targetY - m.y) < 300).length;
    let witchCount = ownedSpecialFishes.witch;

    if (nearbyGarbage > 0) {
        let drain = 1.2 * nearbyGarbage * Math.max(0.2, 1.0 - witchCount * 0.3);
        waterQuality -= drain;
    } else {
        waterQuality += Math.random() * 1.3 + 1.2;
    }

    if (isPumping) {
        waterQuality += Math.random() * 1.5 + 2.5;
        gold += 1;
    } else {
        gold += 2;
    }

    waterQuality = Math.max(0.0, Math.min(maxWaterQuality, waterQuality));

    monsterSpawnTimer++;
    if (monsterSpawnTimer >= 3) {   // 몬스터 스폰 주기 6초 -> 3초로 변경
        monsterSpawnTimer = 0;
        if (monsters.length < 25) spawnMonster();  // 게임 내 쓰레기 최대 수 15 -> 25
    }

    let ghostCount = ownedSpecialFishes.ghost;
    if (ghostCount > 0) {
        ghostGoldTimer++;
        if (ghostGoldTimer >= 10) {
            ghostGoldTimer = 0;
            let bonus = 15 * ghostCount;
            gold += bonus;
            showInGameMessage(`👻 유령 가재 청소 보너스! (+${bonus}G)`);
        }
    }
}, 1000);

function batterySummaryText() {
    if (!batteryStatus) return "🔋 배터리: 데이터 없음";
    const labels = { thruster1: "추진1", thruster2: "추진2", pump_ctrl: "펌프/제어", sensor_board: "센서" };
    let parts = [];
    for (const key of Object.keys(labels)) {
        const item = batteryStatus[key];
        if (!item) continue;
        const pct = item.percentage;
        const warn = (pct !== undefined && pct < batteryWarningPct) ? "⚠" : "";
        parts.push(`${labels[key]} ${pct ?? '-'}%${warn}`);
    }
    return parts.length ? `🔋 ${parts.join(' ')}` : "🔋 배터리: 데이터 없음";
}

// --- [화면 맞춤] 메인/엔딩 화면은 800x600 고정 그림이라 그대로 두고, 실제 조종 화면(game)만
// 스크롤되는 넓은 맵을 더 보여주도록 캔버스 내부 가로 해상도를 창 크기에 맞춰 늘린다.
// 세로(600) 기준 좌표 로직은 그대로 두고, #gameContainer를 그 비율로 확대해서 창을 꽉 채운다
// (모니터 해상도와 무관하게, 매 프레임 창 크기를 확인해서 동작).
function updateResponsiveCanvas() {
    // 카메라/펌프제어 패널은 조종 화면(game)에서만 보여준다 - 메인/엔딩 화면에서는 숨김.
    const inGame = (gameState === "game");
    document.getElementById('cameraPanel').classList.toggle('panel-hidden', !inGame || !SHOW_CAMERA);
    document.getElementById('actuatorPanel').classList.toggle('panel-hidden', !inGame);

    const fillScale = window.innerHeight / canvas.height;
    const desiredWidth = (gameState === "game")
        ? Math.max(800, Math.round(window.innerWidth / fillScale))
        : 800;
    if (canvas.width !== desiredWidth) {
        canvas.width = desiredWidth;
    }

    const scale = Math.min(window.innerWidth / (canvas.width + 6), window.innerHeight / (canvas.height + 6));
    document.getElementById('gameContainer').style.transform = `scale(${scale})`;

    // 사이드바(HUD)는 항상 캔버스 우측 230px 폭 고정 - 캔버스가 넓어지면 그만큼 오른쪽으로 밀림.
    // #cameraPanel은 왼쪽 열(미니맵 아래)에 고정이라 따로 옮길 필요 없지만, #actuatorPanel은
    // 사이드바 안(수질 센서 패널과 뽑기 패널 사이)에 들어있어서 sidebarX를 따라가야 한다.
    const sidebarX = canvas.width - 230;
    document.getElementById('actuatorPanel').style.left = (sidebarX + 15) + 'px';

    // 호수(월드) 폭도 뷰포트(sidebarX)만큼 늘려서 배경 이미지가 빈틈없이 다 채우도록 한다.
    mapWidth = Math.max(1140, sidebarX);
}

// --- [조이스틱 뽑기 버튼] 하드웨어 조이스틱 버튼이 물고기 4종을 개별로 고르기엔
// 부족해서, 뽑기 자체를 버튼 하나(X)에 배정한다. ROS의 /joy 토픽과는 별개로 브라우저가
// 직접 인식하는 HTML5 Gamepad API(navigator.getGamepads)를 사용한다 - 이벤트가 아니라
// 매 프레임 폴링해야 버튼 상태를 읽을 수 있는 API라서 mainLoop 안에서 호출한다. ---
const GACHA_GAMEPAD_BUTTON_INDEX = 3; // X 버튼 (실측 확인 완료)
let prevGachaButtonPressed = false;

function pollGamepadForGacha() {
    if (gameState !== "game" || activeCardShown) {
        prevGachaButtonPressed = false;
        return;
    }

    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    const pad = pads[0]; // 첫 번째로 연결된 조이스틱만 사용
    const button = pad && pad.buttons[GACHA_GAMEPAD_BUTTON_INDEX];
    const pressed = !!(button && button.pressed);

    if (pressed && !prevGachaButtonPressed) {
        rollGachaFish(); // 버튼을 누르는 순간(edge)에만 1회 실행 - 누르고 있어도 연속 실행 안 됨
    }
    prevGachaButtonPressed = pressed;
}

// --- [조이스틱 게임 시작 버튼] 메인 화면에서 마우스로 START 안내 문구를 누르는 대신
// 조이스틱의 Start 버튼으로 시작할 수 있게 한다. 버튼 인덱스 9번 = 실제 조이스틱으로
// 실측 확인 완료 (Start 버튼). ---
const START_GAMEPAD_BUTTON_INDEX = 9; // 실측 확인 완료
let prevStartButtonPressed = false;

function pollGamepadForStart() {
    if (gameState !== "main") {
        prevStartButtonPressed = false;
        return;
    }

    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    const pad = pads[0];
    const button = pad && pad.buttons[START_GAMEPAD_BUTTON_INDEX];
    const pressed = !!(button && button.pressed);

    if (pressed && !prevStartButtonPressed) {
        startGame(); // 누르는 순간(edge)에만 1회 실행
    }
    prevStartButtonPressed = pressed;
}

// --- [조이스틱 back 버튼] 엔딩 화면에서 마우스로 "메인 화면으로 돌아가기"를 누르는
// 대신 조이스틱의 Back 버튼으로 돌아갈 수 있게 한다. 버튼 인덱스 8 = 표준 Gamepad API
// 매핑상 Back/Select 버튼 추정치 - 실제 조이스틱으로 검증 필요(안 맞으면 콘솔에서
// navigator.getGamepads()[0].buttons를 눌러보며 pressed 인덱스 확인). ---
const BACK_GAMEPAD_BUTTON_INDEX = 8;
let prevBackButtonPressed = false;

function pollGamepadForBack() {
    if (gameState !== "ending") {
        prevBackButtonPressed = false;
        return;
    }

    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    const pad = pads[0];
    const button = pad && pad.buttons[BACK_GAMEPAD_BUTTON_INDEX];
    const pressed = !!(button && button.pressed);

    if (pressed && !prevBackButtonPressed) {
        gameState = "main"; // 누르는 순간(edge)에만 1회 실행
        playBgm("main");
    }
    prevBackButtonPressed = pressed;
}

let animTimer = 0;
function mainLoop() {
    pollGamepadForGacha();
    pollGamepadForStart();
    pollGamepadForBack();
    updateResponsiveCanvas();
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (gameState === "main") {
        if (assets.mainstart.complete && assets.mainstart.naturalWidth !== 0) {
            ctx.drawImage(assets.mainstart, 0, 0, 800, 600);
        } else {
            ctx.fillStyle = "#1a1a1a";
            ctx.fillRect(0, 0, 800, 600);
        }

        ctx.fillStyle = "#2c1a11";
        ctx.font = "bold 36px '맑은 고딕'";
        ctx.textAlign = "center";
        ctx.fillText("우당탕탕 호수 지키기", 402, 91);
        ctx.fillStyle = "#fff3d1";
        ctx.fillText("우당탕탕 호수 지키기", 400, 90);

        ctx.fillStyle = "#150d08";
        ctx.font = "bold 12px '맑은 고딕'";
        ctx.fillText("🎯 쓰레기는 시원하게 치우고, 물고기 친구들을 데려오자!", 401, 151);
        ctx.fillStyle = "#ffffff";
        ctx.fillText("🎯 쓰레기는 시원하게 치우고, 물고기 친구들을 데려오자!", 400, 150);

        // START 안내 텍스트 - 예전엔 이 위에 클릭용 "게임 화면 시작" 박스가 따로 있었는데
        // 없애고, 이 문구 자체를 버튼처럼 쓴다. 배경 그림 속 캐릭터 말풍선이 화면 중앙(y~230
        // 부근)에 있어서 그 자리에 겹치지 않도록 화면 아래쪽 빈 공간으로 옮겼다.
        ctx.fillStyle = "#150d08";
        ctx.font = "bold 18px '맑은 고딕'";
        ctx.fillText("[START] 버튼을 눌러 게임을 시작하세요!", 401, 561);
        ctx.fillStyle = "#fff3d1";
        ctx.fillText("[START] 버튼을 눌러 게임을 시작하세요!", 400, 560);

        ctx.textAlign = "left";

        drawCornerLogos(598);

    } else if (gameState === "game") {
        animTimer += 0.2;

        // /cmd_vel(조이스틱 → joy_to_cmd_node의 실제 명령, /api/state로 폴링)의 부호를
        // 화면 방향(dx,dy)으로 역변환해서 보트가 바라보는 방향/스프라이트에만 반영한다.
        // 위치 자체는 /gps/fix가 갱신(refreshState).
        const CMD_VEL_EPS = 0.05;
        const isMoving = Math.abs(lastCmdVel.linearX) > CMD_VEL_EPS || Math.abs(lastCmdVel.angularZ) > CMD_VEL_EPS;

        if (isMoving) {
            if (activeCardShown) hideFishCardPopup();

            let dy = lastCmdVel.linearX > CMD_VEL_EPS ? -1 : (lastCmdVel.linearX < -CMD_VEL_EPS ? 1 : 0);
            let dx = lastCmdVel.angularZ > CMD_VEL_EPS ? 1 : (lastCmdVel.angularZ < -CMD_VEL_EPS ? -1 : 0);

            boatAngle = Math.atan2(dy, dx);

            // 8방향 조합에 따른 스프라이트 프레임 지정 (시트 순서에 맞춤)
            if (dx === 0 && dy < 0) {
                boatSpriteIndex = 0; // 위
            } else if (dx > 0 && dy < 0) {
                boatSpriteIndex = 2; // 우상
            } else if (dx > 0 && dy === 0) {
                boatSpriteIndex = 4; // 우
            } else if (dx > 0 && dy > 0) {
                boatSpriteIndex = 6; // 우하
            } else if (dx === 0 && dy > 0) {
                boatSpriteIndex = 8; // 아래
            } else if (dx < 0 && dy > 0) {
                boatSpriteIndex = 10; // 좌하
            } else if (dx < 0 && dy === 0) {
                boatSpriteIndex = 12; // 좌
            } else if (dx < 0 && dy < 0) {
                boatSpriteIndex = 14; // 좌상
            }

            // GPS 미수신 시 dead-reckoning 폴백: 조이스틱 입력 방향으로 화면상 위치를 직접 이동
            // (GPS가 들어오는 순간 refreshState()가 targetX/Y를 덮어써서 자연히 GPS 기준으로 전환됨)
            if (!isGpsReceived) {
                let speed = 3.5; // 조이스틱 입력에 따른 화면상 보트 이동 속도 (기존 6.0에서 낮춤)
                let len = Math.hypot(dx, dy);
                targetX = Math.max(30, Math.min(targetX + (dx / len) * speed, mapWidth - 30));
                targetY = Math.max(30, Math.min(targetY + (dy / len) * speed, mapHeight - 30));
            }
        }

        // 사이드바(HUD)는 캔버스 우측 230px 고정, 나머지가 호수(플레이 뷰포트) 폭.
        // 캔버스가 창 크기에 맞춰 넓어지면 호수도 그만큼 더 넓게 보인다 (updateResponsiveCanvas 참고).
        const sidebarX = canvas.width - 230;
        const lakeWidth = sidebarX;

        let cameraX = Math.max(0, Math.min(targetX - lakeWidth / 2, mapWidth - lakeWidth));
        let cameraY = Math.max(0, Math.min(targetY - 300, mapHeight - 600));

        // 1. 배경(호수)
        if (assets.lake.complete && assets.lake.naturalWidth !== 0) {
            ctx.drawImage(assets.lake, -cameraX, -cameraY, mapWidth, mapHeight);
        } else {
            ctx.fillStyle = "#4078b4";
            ctx.fillRect(0, 0, lakeWidth, 600);
        }

        // 2. 물고기
        fishes.forEach(fish => {
            fish.x += 1.2 * fish.dir;
            if (fish.x > mapWidth - 50) fish.dir = -1;
            else if (fish.x < 50) fish.dir = 1;
            fish.y += Math.sin(fish.x * 0.05 + animTimer) * 0.3;

            let fx = fish.x - cameraX;
            let fy = fish.y - cameraY;
            if (fx >= -30 && fx <= lakeWidth + 30 && fy >= -30 && fy <= 630) {
                if (assets.pixelFishes.complete && assets.pixelFishes.naturalWidth !== 0) {
                    let cols = 9;
                    let cellW = assets.pixelFishes.naturalWidth / cols;
                    let cellH = assets.pixelFishes.naturalHeight / 8;
                    let c = fish.type % cols;
                    let r = Math.floor(fish.type / cols);
                    ctx.drawImage(assets.pixelFishes, c * cellW, r * cellH, cellW, cellH, fx - 12, fy - 12, 24, 24);
                } else {
                    ctx.fillStyle = "#ffd166";
                    ctx.beginPath();
                    ctx.arc(fx, fy, 10, 0, Math.PI * 2);
                    ctx.fill();
                }
            }
        });

        // 3. 쓰레기
        let beamWorldX = targetX + Math.cos(boatAngle) * 85;
        let beamWorldY = targetY + Math.sin(boatAngle) * 85;

        monsters.forEach(m => {
            let size = m.isLarge ? 44 : 28;
            let half = size / 2;
            let mx = m.x - cameraX;
            let my = m.y - cameraY;
            if (mx >= -30 && mx <= lakeWidth + 30 && my >= -30 && my <= 630) {
                if (m.photo.complete && m.photo.naturalWidth !== 0) {
                    ctx.drawImage(m.photo, mx - half, my - half, size, size);
                } else {
                    ctx.fillStyle = "#888";
                    ctx.fillRect(mx - half, my - half, size, size);
                }
            }

            if (isPumping) {
                let dist = Math.hypot(beamWorldX - m.x, beamWorldY - m.y);
                if (dist < 75) {
                    m.hp -= 1;
                    if (m.hp <= 0) {
                        let idx = monsters.indexOf(m);
                        if (idx > -1) monsters.splice(idx, 1);
                        let reward = m.isLarge
                            ? Math.floor(Math.random() * 31) + 60  // 큰 쓰레기는 보상도 더 크게 (60~90G)
                            : Math.floor(Math.random() * 16) + 15;
                        gold += reward;
                        playSfx("trash");
                        playSfx("coin");
                        showInGameMessage(`✨ 쓰레기 수거 성공! (+${reward}G)`);
                    }
                }
            }
        });

        // 4. 물대포 이펙트 + 펌프 소리
        if (isPumping) {
            if (sfx.pump.paused) sfx.pump.play().catch(() => {});
        } else {
            sfx.pump.pause(); sfx.pump.currentTime = 0;
        }

        if (isPumping) {
            ctx.save();
            ctx.translate(beamWorldX - cameraX, beamWorldY - cameraY);
            ctx.rotate(boatAngle);
            ctx.globalCompositeOperation = 'screen';
            if (assets.waterArrow.complete && assets.waterArrow.naturalWidth !== 0) {
                ctx.drawImage(assets.waterArrow, -70, -25, 140, 50);
            } else {
                ctx.fillStyle = "#38bdf8";
                ctx.fillRect(0, -10, 50, 20);
            }
            ctx.restore();
        }

        // 5. 보트 스프라이트 출력 및 오로라 배경 투명화 적용 (1번 코드와 동일)
        let screenBoatX = targetX - cameraX;
        let screenBoatY = targetY - cameraY;

        // 실제 수질 센서(clarity_pct, /water_quality/data)를 따른다 - 게임 내부 시뮬레이션
        // 변수인 waterQuality(점수/연출용)와는 별개다. 기준은 usv_actuators의 water_policy.py와
        // 동일: 60 이상 좋음/초록, 40 미만 나쁨/빨강, 그 사이 보통/노랑.
        let currentAuraImg = assets.green;
        if (sensorWQ.clarity_pct !== null && sensorWQ.clarity_pct !== undefined) {
            if (sensorWQ.clarity_pct < 40) {
                currentAuraImg = assets.red;
            } else if (sensorWQ.clarity_pct < 60) {
                currentAuraImg = assets.yellow;
            }
        }

        if (currentAuraImg.complete && currentAuraImg.naturalWidth !== 0) {
            let tempAuraCanvas = document.createElement('canvas');
            tempAuraCanvas.width = currentAuraImg.naturalWidth;
            tempAuraCanvas.height = currentAuraImg.naturalHeight;
            let tAuraCtx = tempAuraCanvas.getContext('2d');

            tAuraCtx.drawImage(currentAuraImg, 0, 0);

            try {
                let imgData = tAuraCtx.getImageData(0, 0, tempAuraCanvas.width, tempAuraCanvas.height);
                let data = imgData.data;
                for (let i = 0; i < data.length; i += 4) {
                    let r = data[i], g = data[i+1], b = data[i+2];

                    // 오로라 본연의 색상은 보호하고, 순수한 흰색 배경(250 이상)만 투명하게 제거
                    if (r > 250 && g > 250 && b > 250) {
                        data[i+3] = 0;
                    }
                }
                tAuraCtx.putImageData(imgData, 0, 0);

                ctx.save();
                ctx.globalAlpha = 0.9; 
                let auraSize = 95;
                ctx.drawImage(tempAuraCanvas, screenBoatX - auraSize / 2, screenBoatY - auraSize / 2, auraSize, auraSize);
                ctx.restore();
            } catch (err) {
                ctx.save();
                ctx.globalAlpha = 0.9;
                ctx.drawImage(currentAuraImg, screenBoatX - 47, screenBoatY - 47, 95, 95);
                ctx.restore();
            }
        }

        if (assets.ship.complete && assets.ship.naturalWidth !== 0) {
            let sw = assets.ship.naturalWidth;
            let sh = assets.ship.naturalHeight;
            let frameW = sw / 16;

            let tempCanvas = document.createElement('canvas');
            tempCanvas.width = frameW;
            tempCanvas.height = sh;
            let tCtx = tempCanvas.getContext('2d');

            tCtx.drawImage(assets.ship, boatSpriteIndex * frameW, 0, frameW, sh, 0, 0, frameW, sh);

            try {
                let imgData = tCtx.getImageData(0, 0, frameW, sh);
                let data = imgData.data;
                for (let i = 0; i < data.length; i += 4) {
                    if (data[i] > 240 && data[i+1] > 240 && data[i+2] > 240) {
                        data[i+3] = 0;
                    }
                }
                tCtx.putImageData(imgData, 0, 0);

                ctx.drawImage(tempCanvas, 0, 0, frameW, sh, screenBoatX - 27, screenBoatY - 27, 54, 54);
            } catch (err) {
                ctx.drawImage(tempCanvas, 0, 0, frameW, sh, screenBoatX - 27, screenBoatY - 27, 54, 54);
            }
        } else {
            ctx.fillStyle = "#ff5722";
            ctx.beginPath();
            ctx.arc(screenBoatX, screenBoatY, 20, 0, Math.PI * 2);
            ctx.fill();
        }

        // 6. 우측 UI 패널 영역
        ctx.fillStyle = "#2c1a11";
        ctx.fillRect(sidebarX, 0, 230, 600);
        ctx.strokeStyle = "#1c100a";
        ctx.lineWidth = 5;
        ctx.strokeRect(sidebarX, 0, 230, 600);

        let mins = String(Math.floor(timeLeft / 60)).padStart(2, '0');
        let secs = String(timeLeft % 60).padStart(2, '0');

        ctx.fillStyle = "#ff4757";
        ctx.font = "bold 14px 'Courier New'";
        ctx.textAlign = "center";
        ctx.fillText(`⏱️ ${mins}:${secs}`, sidebarX + 115, 30);

        ctx.fillStyle = "#2ed573";
        ctx.font = "bold 13px '맑은 고딕'";
        ctx.fillText(`🏆 ${score} / ${targetScore}`, sidebarX + 115, 55);

        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 13px '맑은 고딕'";
        ctx.fillText(`💰 ${gold} G`, sidebarX + 115, 80);

        // 💧 수질 센서 정보 패널 (실제 /water_quality/data 스키마: temp_c/ph/do_mg_l/
        // turbidity_voltage_v/clarity_pct/clarity_level 그대로 표시)
        ctx.fillStyle = "#1c100a";
        ctx.strokeStyle = "#ffd166";
        ctx.lineWidth = 2;
        ctx.fillRect(sidebarX + 15, 95, 200, 145);
        ctx.strokeRect(sidebarX + 15, 95, 200, 145);

        ctx.fillStyle = "#ffd166";
        ctx.font = "bold 11px '맑은 고딕'";
        ctx.fillText("[ USV 수질 센서 모니터링 ]", sidebarX + 115, 115);

        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 11px '맑은 고딕'";
        ctx.fillText(`등급: ${sensorWQ.clarity_level ?? '-'}`, sidebarX + 115, 138);

        ctx.font = "10px '맑은 고딕'";
        ctx.fillStyle = "#4cc9f0";
        ctx.fillText(`✨ 맑기: ${sensorWQ.clarity_pct ?? '-'}%  (탁도 ${sensorWQ.turbidity_voltage_v ?? '-'}V)`, sidebarX + 115, 160);
        ctx.fillStyle = "#38bdf8";
        ctx.fillText(`🌡️ 수온: ${sensorWQ.temp_c ?? '-'} °C   pH ${sensorWQ.ph ?? '-'}`, sidebarX + 115, 180);
        ctx.fillStyle = "#2ed573";
        ctx.fillText(`🫧 용존산소: ${sensorWQ.do_mg_l ?? '-'} mg/L`, sidebarX + 115, 200);

        // 산타 물고기 효과(적정 수질 시 점수 배율)는 게임 자체 waterQuality 변수를 그대로 씀.
        // 이 게이지 바는 맑기(%)를 시각화만 하는 용도.
        let ratio = Math.max(0, Math.min(1, (sensorWQ.clarity_pct ?? 0) / 100.0));
        ctx.fillStyle = "#0f0906";
        ctx.strokeStyle = "#8b5a2b";
        ctx.lineWidth = 1;
        ctx.fillRect(sidebarX + 35, 212, 160, 12);
        ctx.strokeRect(sidebarX + 35, 212, 160, 12);

        ctx.fillStyle = "#06d6a0";
        ctx.fillRect(sidebarX + 36, 213, intRange(158 * ratio), 10);

        ctx.fillStyle = "#ffffff";
        ctx.font = "9px '맑은 고딕'";
        ctx.fillText(batterySummaryText(), sidebarX + 115, 236);

        // 뽑기 패널 (조이스틱 버튼 하나로 실행 가능한 단일 뽑기 버튼 + 등급표)
        // 수질 센서 패널과의 사이에 펌프제어 패널(#actuatorPanel, DOM)이 끼어들면서
        // 기존보다 90px 아래로 밀려났다.
        ctx.fillStyle = "#150d08";
        ctx.strokeStyle = "#e29578";
        ctx.lineWidth = 2;
        ctx.fillRect(sidebarX + 15, 350, 200, 210);
        ctx.strokeRect(sidebarX + 15, 350, 200, 210);

        ctx.fillStyle = "#ffd166";
        ctx.font = "bold 11px '맑은 고딕'";
        ctx.fillText("🎰 랜덤 물고기 뽑기", sidebarX + 115, 370);

        // 뽑기 버튼 - 마우스 클릭(클릭 핸들러 참고) 또는 조이스틱 버튼(pollGamepadForGacha)으로 실행
        ctx.fillStyle = "#3a2214";
        ctx.strokeStyle = "#ffd166";
        ctx.lineWidth = 1;
        ctx.fillRect(sidebarX + 25, 380, 180, 36);
        ctx.strokeRect(sidebarX + 25, 380, 180, 36);
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 12px '맑은 고딕'";
        ctx.fillText(`✨ 뽑기 (${GACHA_COST}G) ✨`, sidebarX + 115, 402);

        ctx.fillStyle = "#a5a5a5";
        ctx.font = "9px '맑은 고딕'";
        ctx.fillText("(조이스틱 X 버튼으로도 실행 가능)", sidebarX + 115, 430);

        ctx.fillStyle = "#ffd166";
        ctx.font = "bold 10px '맑은 고딕'";
        ctx.fillText("[ 등급표 ]", sidebarX + 115, 448);

        let rarityRows = ["witch", "ghost", "santa", "pumpkin"].map((key, i) => ({
            key, y: 464 + i * 18
        }));
        ctx.font = "9px '맑은 고딕'";
        rarityRows.forEach(row => {
            let info = specialFishTemplates[row.key];
            ctx.fillStyle = "#ffffff";
            ctx.fillText(`${info.rarity} · ${info.kor_name} +${info.score_val}점/초 (${info.chance}%)`, sidebarX + 115, row.y);
        });

        // 7. 좌측 상단 미니맵
        ctx.fillStyle = "#1c100a";
        ctx.strokeStyle = "#ffd166";
        ctx.lineWidth = 2;
        ctx.fillRect(10, 10, 140, 165);
        ctx.strokeRect(10, 10, 140, 165);

        if (miniMapImg.complete && miniMapImg.naturalWidth !== 0) {
            ctx.drawImage(miniMapImg, 15, 15, 130, 137);
        } else {
            ctx.fillStyle = "#4078b4";
            ctx.fillRect(15, 15, 130, 137);
        }

        monsters.forEach(m => {
            let mxMini = 15 + (m.x / mapWidth) * 130;
            let myMini = 15 + (m.y / mapHeight) * 137;
            ctx.fillStyle = "#ff4757";
            ctx.beginPath();
            ctx.arc(mxMini, myMini, 2, 0, Math.PI * 2);
            ctx.fill();
        });

        let bxMini = 15 + (targetX / mapWidth) * 130;
        let byMini = 15 + (targetY / mapHeight) * 137;
        ctx.fillStyle = "#38bdf8";
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(bxMini, byMini, 3, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = "#55ff55";
        ctx.font = "bold 9px 'Courier New'";
        ctx.fillText(`X: ${Math.floor(targetX)}, Y: ${Math.floor(targetY)}`, 80, 162);

        // 8. 알림 메시지 (호수 뷰포트 폭 기준으로 가로 중앙 정렬)
        const lakeCenterX = lakeWidth / 2;
        if (notificationText !== "") {
            ctx.fillStyle = "#150d08";
            ctx.strokeStyle = "#4ade80";
            ctx.lineWidth = 2;
            ctx.fillRect(lakeCenterX - 225, 515, 450, 50);
            ctx.strokeRect(lakeCenterX - 225, 515, 450, 50);

            ctx.fillStyle = "#ffffff";
            ctx.font = "bold 12px '맑은 고딕'";
            ctx.fillText(notificationText, lakeCenterX, 545);
        }

        // 8-1. 퀘스트 안내 텍스트 (좌측 하단)
        ctx.fillStyle = "rgba(0,0,0,0.5)";
        ctx.fillRect(10, 390, 145, 148);
        ctx.strokeStyle = "#ffd166";
        ctx.lineWidth = 1;
        ctx.strokeRect(10, 390, 145, 148);

        ctx.fillStyle = "#ffd166";
        ctx.font = "bold 11px '맑은 고딕'";
        ctx.textAlign = "left";
        ctx.fillText("[퀘스트 1] 푸른 호수 클리어!", 15, 408);
        ctx.fillStyle = "#ffffff";
        ctx.font = "10px '맑은 고딕'";
        ctx.fillText("목표: [B]펌프 모드 변경 후", 15, 425);
        ctx.fillText("[A]눌러 펌프 작동→쓰레기 제거!", 15, 440);
        ctx.fillStyle = "#2ed573";
        ctx.fillText("보상: 친환경 점수 + 코인 획득", 15, 455);

        ctx.fillStyle = "#ffd166";
        ctx.font = "bold 11px '맑은 고딕'";
        ctx.fillText("[퀘스트 2] 동료를 찾아라!", 15, 475);
        ctx.fillStyle = "#ffffff";
        ctx.font = "10px '맑은 고딕'";
        ctx.fillText("목표: [X]눌러 코인으로", 15, 492);
        ctx.fillText("랜덤 물고기 뽑기!", 15, 507);
        ctx.fillStyle = "#2ed573";
        ctx.fillText("보상: 물고기마다 보너스 점수", 15, 522);

        // 8-2. 물고기 능력 설명 (퀘스트 칸 바로 밑)
        ctx.fillStyle = "rgba(0,0,0,0.5)";
        ctx.fillRect(10, 540, 145, 58);
        ctx.strokeStyle = "#4cc9f0";
        ctx.lineWidth = 1;
        ctx.strokeRect(10, 540, 145, 58);

        ctx.fillStyle = "#4cc9f0";
        ctx.font = "bold 11px '맑은 고딕'";
        ctx.fillText("[물고기 능력]", 15, 554);

        // 세로 공간이 좁아서 4줄로 쭉 나열하는 대신 2x2 칸에 나눠 담아, 퀘스트 칸과
        // 같은 크기(10px)의 글씨를 써도 박스 안에 다 들어가게 한다.
        ctx.textAlign = "center";
        ctx.fillStyle = "#ffffff";
        ctx.font = "10px '맑은 고딕'";
        const abilityCellW = 145 / 2;
        [
            { x: 10, y: 570, text: "🎩 피해 -30%" },
            { x: 10 + abilityCellW, y: 570, text: "👻 +15G/10초" },
            { x: 10, y: 586, text: "🎅 점수 x1.4" },
            { x: 10 + abilityCellW, y: 586, text: "👑 +50점/초" }
        ].forEach(({ x: cx, y: cy, text }) => {
            ctx.fillText(text, cx + abilityCellW / 2, cy);
        });

        ctx.textAlign = "center";

        // 9. 특별 물고기 영입 카드 팝업
        if (activeCardShown && activeCardKey) {
            ctx.fillStyle = "rgba(0,0,0,0.5)";
            ctx.fillRect(0, 0, lakeWidth, 600);

            const cardX = lakeCenterX - 110;
            ctx.fillStyle = "#110a05";
            ctx.strokeStyle = "#e29578";
            ctx.lineWidth = 3;
            ctx.fillRect(cardX, 105, 220, 330);
            ctx.strokeRect(cardX, 105, 220, 330);

            ctx.fillStyle = "#ffd166";
            ctx.font = "bold 10px 'Courier New'";
            ctx.fillText(`★  ${specialFishTemplates[activeCardKey].rarity}  ★`, lakeCenterX, 125);

            ctx.fillStyle = "#ffffff";
            ctx.font = "bold 12px 'Courier New'";
            ctx.fillText(specialFishTemplates[activeCardKey].kor_name, lakeCenterX, 150);

            if (assets.fourFish.complete && assets.fourFish.naturalWidth !== 0) {
                let fw = assets.fourFish.naturalWidth;
                let fh = assets.fourFish.naturalHeight;
                let midX = fw / 2, midY = fh / 2;
                let boxes = {
                    witch: [0, 0, midX, midY],
                    ghost: [midX, 0, midX, midY],
                    santa: [0, midY, midX, midY],
                    pumpkin: [midX, midY, midX, midY]
                };
                let b = boxes[activeCardKey];
                ctx.drawImage(assets.fourFish, b[0], b[1], b[2], b[3], cardX + 30, 175, 160, 160);
            }

            ctx.fillStyle = "#a5a5a5";
            ctx.font = "bold 10px '맑은 고딕'";
            ctx.fillText(specialFishTemplates[activeCardKey].desc, lakeCenterX, 370);

            ctx.strokeStyle = "#e29578";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(cardX + 30, 415);
            ctx.lineTo(cardX + 190, 415);
            ctx.stroke();
        }

        ctx.textAlign = "left";

    } else if (gameState === "ending") {
        if (assets.ending.complete && assets.ending.naturalWidth !== 0) {
            ctx.drawImage(assets.ending, 0, 0, 800, 600);
        } else {
            ctx.fillStyle = "#1890ff";
            ctx.fillRect(0, 0, 800, 600);
        }

        // 이번 판 결과(점수/시간/수집한 물고기 종류별 개수)를 카드 하나로 꽉 채워 보여준다.
        drawResultPanel(230, 275, 340, 210);

        // BACK 안내 텍스트 (우측 하단) - 마우스로도 클릭 가능(클릭 핸들러 참고)
        ctx.fillStyle = "#ffffff";
        ctx.font = "11px '맑은 고딕'";
        ctx.textAlign = "right";
        ctx.fillText("[BACK] 메인화면", 790, 585);

        ctx.textAlign = "left";

        drawCornerLogos(565, 15); // 세로로 쌓으면 꽤 높아져서, "[BACK]" 텍스트(y≈574~585)를 피해 배치. 오른쪽 끝에 딱 붙지 않게 여백을 둠

    }

    requestAnimationFrame(mainLoop);
}

function intRange(val) {
    return Math.max(0, Math.floor(val));
}

requestAnimationFrame(mainLoop);
</script>
</body>
</html>
"""