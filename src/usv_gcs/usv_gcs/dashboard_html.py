"""gui_main_node가 제공하는 웹 대시보드 HTML과 JavaScript."""

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
  /* 테두리는 패널 좌표가 어긋나지 않도록 컨테이너에 둔다. */
  #gameContainer {
      position: relative; display: inline-block; transform-origin: center center;
      border: 3px solid #e29578; box-shadow: 0 0 20px rgba(0,0,0,0.8);
  }
  canvas { display: block; background-color: #2c1a11; }

  #cameraPanel {
      /* 미니맵 아래 왼쪽 열 */
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

  #ledPanel {
      /* 우측 사이드바 위치는 updateResponsiveCanvas()가 갱신한다. */
      position: absolute; top: 248px; left: 585px; width: 200px; height: 32px;
      box-sizing: border-box; display: flex; align-items: center; gap: 6px;
      background-color: #150d08; border: 2px solid #e29578; padding: 0 8px; font-size: 11px;
      z-index: 10; cursor: pointer;
  }
  #ledPanel:hover { background-color: #1c100a; }
  #ledPanel .title {
      color: #ffd166; font-weight: bold;
  }
  .led-toggle-light {
      width: 10px; height: 10px; border-radius: 50%; background: #555;
      box-shadow: inset 0 0 2px rgba(0,0,0,0.8); margin-left: auto; flex-shrink: 0;
  }
  .led-toggle-light.on { background: #3ddc55; box-shadow: 0 0 6px 2px rgba(61,220,85,0.8); }
  .led-toggle-label { font-size: 10px; color: #ccc; font-weight: bold; }

  #actuatorPanel {
      /* LED 패널 아래의 제어 영역 */
      position: absolute; top: 288px; left: 585px; width: 200px; box-sizing: border-box;
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
  .gamepad-btn-badge.badge-blue { background: #2f86eb; }
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
    <canvas id="gameCanvas" width="800" height="600"></canvas>

    <div id="cameraPanel" class="panel-hidden">
        <div class="cam-box" id="surfaceCamBox">
            <span class="cam-title">📷 수면 (Surface)</span>
            <img id="surfaceCam" alt="수면 카메라 연결 중..." onerror="this.style.opacity=0.3">
        </div>
        <div class="cam-box" id="underwaterCamBox">
            <span class="cam-title">🌊 수중 (Underwater)</span>
            <img id="underwaterCam" alt="수중 카메라 연결 중..." onerror="this.style.opacity=0.3">
        </div>
    </div>

    <div id="ledPanel" class="panel-hidden" onclick="toggleLed()">
        <span class="gamepad-btn-badge badge-blue">X</span><span class="title">LED 제어</span>
        <span class="led-toggle-light" id="ledToggleLight"></span>
        <span class="led-toggle-label" id="ledToggleLabel">--</span>
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

<!-- LED 이펙트를 메인 캔버스에 그리기 위한 숨김 호스트 -->
<div id="ledEffectHost" style="position:absolute; left:-9999px; top:-9999px; width:300px; height:300px; pointer-events:none;"></div>

<script src="lottie.min.js"></script>
<script>
// ===== 사용자 설정: 화면, 게임, 조이스틱 =====
const SHOW_SURFACE_CAM = true;
const SHOW_UNDERWATER_CAM = true;
const CAMERA_PORT = 8000;             // B1 카메라 스트림 포트
const GPS_DEFAULT_LAT = 37.3898;     // GPS 수신 전 미니맵 중심
const GPS_DEFAULT_LNG = 126.6390;
const MINI_MAP_REFRESH_MS = 1000;
const STATE_REFRESH_MS = 200;
const CMD_VEL_EPS = 0.05;
const BOAT_SPEED_PX = 2.0;
const GAME_DURATION_SECONDS = 60;
const TARGET_SCORE = 10000;
const INITIAL_GOLD = 300;
const INITIAL_FISH_COUNT = 4;
const LARGE_TRASH_CHANCE = 0.25;
const MONSTER_SPAWN_INTERVAL_SECONDS = 3;
const MAX_MONSTERS = 25;
const MIN_MAP_WIDTH = 1140;
const MAP_HEIGHT = 1200;
const GACHA_COST = 150;
const GACHA_GAMEPAD_BUTTON_INDEX = 2; // Y: 컨트롤러별 확인 필요
const LED_GAMEPAD_BUTTON_INDEX = 3;   // X
const START_GAMEPAD_BUTTON_INDEX = 9; // Start
const BACK_GAMEPAD_BUTTON_INDEX = 8;  // Back: 컨트롤러별 확인 필요

// 서버에서 주입: camera_host는 gcs_params.yaml/launch 인자,
// Google Maps 키는 git에 올리지 않는 gcs_secrets.yaml에서 설정한다.
const cameraHost = "__CAMERA_HOST__";
const googleApiKey = "__GOOGLE_MAPS_API_KEY__";

// ===== 카메라 =====
const ANY_CAM_SHOWN = SHOW_SURFACE_CAM || SHOW_UNDERWATER_CAM;

function setupCamBox(enabled, boxId, imgId, topic) {
    const box = document.getElementById(boxId);
    if (!enabled) {
        box.classList.add('panel-hidden');
        return;
    }
    if (cameraHost) {
        document.getElementById(imgId).src = `http://${cameraHost}:${CAMERA_PORT}/stream?topic=${topic}`;
    } else {
        const warn = document.createElement('div');
        warn.className = 'cam-warn';
        warn.textContent = 'camera_host 미설정 (gcs_params.yaml)';
        box.appendChild(warn);
    }
}
setupCamBox(SHOW_SURFACE_CAM, 'surfaceCamBox', 'surfaceCam', '/camera/surface/image_raw');
setupCamBox(SHOW_UNDERWATER_CAM, 'underwaterCamBox', 'underwaterCam', '/camera/underwater/image_raw');

// ===== GPS 미니맵: 게임 보트 위치와 별개 =====
const miniMapImg = new Image();
let currentLat = GPS_DEFAULT_LAT;
let currentLng = GPS_DEFAULT_LNG;
let miniMapHasGpsFix = false;
let lastMiniMapUpdateMs = 0;

function updateMiniMapUrl(lat, lng) {
    currentLat = lat ?? currentLat;
    currentLng = lng ?? currentLng;
    miniMapImg.src = `https://maps.googleapis.com/maps/api/staticmap?center=${currentLat},${currentLng}&zoom=17&size=130x137&maptype=satellite&key=${googleApiKey}`;

    miniMapImg.onerror = function() {
        console.error("❌ 구글맵 이미지 로드 실패! API 키, 결제 카드 등록 여부 또는 Static Maps API 활성화를 확인하세요.");
    };
}

updateMiniMapUrl(currentLat, currentLng);

// ===== 서버 상태 =====
let lastCmdVel = { linearX: 0, angularZ: 0 };
function hasBoatMotionCommand() {
    return Math.abs(lastCmdVel.linearX) > CMD_VEL_EPS || Math.abs(lastCmdVel.angularZ) > CMD_VEL_EPS;
}

let sensorWQ = {
    temp_c: null, ph: null, do_mg_l: null,
    turbidity_voltage_v: null, clarity_pct: null, clarity_level: null
};

let batteryStatus = null;
let batteryWarningPct = 20;

async function refreshState() {
    try {
        const res = await fetch('/api/state');
        const s = await res.json();

        if (s.cmd_vel) {
            lastCmdVel.linearX = s.cmd_vel.linear_x;
            lastCmdVel.angularZ = s.cmd_vel.angular_z;
        }

        // gps_fix는 신호가 끊겨도 서버에 마지막 값이 남으므로 현재 Fix만 미니맵에 반영한다.
        miniMapHasGpsFix = Boolean(s.gps_has_fix === true && s.gps_fix &&
            Number.isFinite(s.gps_fix.latitude) && Number.isFinite(s.gps_fix.longitude));
        if (miniMapHasGpsFix) {
            const nowMs = Date.now();
            if (nowMs - lastMiniMapUpdateMs >= MINI_MAP_REFRESH_MS) {
                lastMiniMapUpdateMs = nowMs;
                updateMiniMapUrl(s.gps_fix.latitude, s.gps_fix.longitude);
            }
        }

        if (s.pump_on !== null && s.pump_on !== undefined) {
            isPumping = s.pump_on;
        }

        if (s.auto_mode !== null && s.auto_mode !== undefined) {
            document.getElementById('pumpModeAutoBox').classList.toggle('on', s.auto_mode === true);
            document.getElementById('pumpModeManualBox').classList.toggle('on', s.auto_mode === false);
        }

        if (s.water_quality) {
            sensorWQ = s.water_quality;
        }

        if (s.led_on !== null && s.led_on !== undefined) {
            ledOn = s.led_on;
            updateLedUi();
        }

        batteryStatus = s.battery_status;
        if (s.battery_warning_pct !== undefined) batteryWarningPct = s.battery_warning_pct;
    } catch (e) {
        console.error(e);
    }
}
setInterval(refreshState, STATE_REFRESH_MS);
refreshState();

// ===== LED 이펙트와 조작 =====
const ledEffectAnim = lottie.loadAnimation({
    container: document.getElementById('ledEffectHost'),
    renderer: 'canvas',
    loop: true,
    autoplay: false,
    path: 'led_effect.json'
});
let ledEffectCanvas = null;
ledEffectAnim.addEventListener('DOMLoaded', () => {
    ledEffectCanvas = document.getElementById('ledEffectHost').querySelector('canvas');
});
let ledEffectPlaying = false;

// LED는 이 화면에서 /api/led로 명령을 보낸다.
function updateLedUi() {
    document.getElementById('ledToggleLight').classList.toggle('on', ledOn === true);
    document.getElementById('ledToggleLabel').textContent = ledOn === null ? '--' : (ledOn ? 'ON' : 'OFF');

    if (ledOn === true && !ledEffectPlaying) {
        ledEffectPlaying = true;
        ledEffectAnim.goToAndPlay(0, true);
    } else if (ledOn !== true && ledEffectPlaying) {
        ledEffectPlaying = false;
        ledEffectAnim.pause();
    }
}

function toggleLed() {
    const next = !ledOn;
    ledOn = next; // 화면을 먼저 갱신하고 다음 상태 폴링에서 보정
    updateLedUi();
    fetch('/api/led', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ on: next }),
    }).catch((e) => console.error('LED 명령 전송 실패', e));
}

// 게임 상태는 펌프·자동 모드에만 적용된다. 실제 배 이동은 게임 상태와 무관하다.
function setGameActive(active) {
    ledOn = false;
    updateLedUi();
    fetch('/api/game_active', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ active }),
    }).catch((e) => console.error('game_active 전송 실패', e));
}

const canvas = document.getElementById("gameCanvas");
const ctx = canvas.getContext("2d");

// ===== 이미지 자원 =====
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
    logoYouth: new Image(),
    timeBanner: new Image()
};

// 이미지 파일명 매칭
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
assets.timeBanner.src = "time.png";

// 시작·종료 화면 로고
function drawCornerLogos(bottomY, rightMargin = 15) {
    // 배경판 폭은 통일하고 로고의 원본 비율은 유지한다.
    const commonW = 150;
    const pad = 6;
    const gap = 2;
    // 세로가 긴 인천대 로고는 카드 안에서 축소한다.
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

// ===== 오디오 =====
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

// ===== 게임 상태 =====
let gameState = "main";

let initialTime = GAME_DURATION_SECONDS;
let timeLeft = initialTime;
let targetScore = TARGET_SCORE;
let isGameOver = false;
let cheatClickCount = 0;
let waterQuality = 70.0;
let maxWaterQuality = 100.0;
let gold = INITIAL_GOLD;
let score = 0;
let fishCount = INITIAL_FISH_COUNT;
let ownedSpecialFishes = { witch: 0, ghost: 0, santa: 0, pumpkin: 0 };
let ghostGoldTimer = 0;

// 넓은 화면에서는 updateResponsiveCanvas()가 맵 너비를 늘린다.
let mapWidth = MIN_MAP_WIDTH;
const mapHeight = MAP_HEIGHT;

// 게임 보트는 맵 중앙에서 시작하며 GPS와 연동하지 않는다.
let targetX = mapWidth / 2;
let targetY = mapHeight / 2;

let boatAngle = 0.0;
let boatSpriteIndex = 0;
let isPumping = false;
// LED 명령 직후 화면을 먼저 갱신하고, 다음 서버 폴링에서 실제 상태로 맞춘다.
let ledOn = null;

let fishes = [];
let monsters = [];
let monsterSpawnTimer = 0;
let activeCardShown = false;
let activeCardKey = null;
let cardHideTimer = null;
let notificationText = "";
let notificationTimer = null;

// 뽑기 확률(chance)의 합은 100이어야 한다.
const specialFishTemplates = {
    witch: { name: "WITCH FISH", kor_name: "마녀 피쉬", rarity: "레어", chance: 55, score_val: 15, desc: "쓰레기 패널티 30% 완화 🎩" },
    ghost: { name: "GHOST LOBSTER", kor_name: "유령 가재", rarity: "에픽", chance: 28, score_val: 25, desc: "10초마다 +15G 생산 👻" },
    santa: { name: "SANTA GOLDFISH", kor_name: "산타 금붕어", rarity: "유니크", chance: 13, score_val: 35, desc: "적정 수질 시 점수 1.4배 🎅" },
    pumpkin: { name: "PUMPKIN FISH", kor_name: "호박 왕관피쉬", rarity: "레전더리", chance: 4, score_val: 50, desc: "초당 기본 점수 든든하게 +50점 👑" }
};

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
        // 뽑기 버튼 (사이드바 맨 위 칸, 퀘스트 칸보다 위 - 그리는 쪽 gachaPanelY와
        // 좌표를 맞춰둔 것, canvas.height는 항상 600 고정이라 여기 숫자도 고정값으로 둬도 된다)
        const sidebarX = canvas.width - 230;
        if (x >= sidebarX + 25 && x <= sidebarX + 205 && y >= 413 && y <= 439) {
            rollGachaFish();
            return;
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

// 엔딩으로 넘어가는 지점이 치트/점수달성/시간초과 3곳이라, gameState 대입만 반복하면
// game_active를 끄는 걸 빠뜨리기 쉬워서 하나로 모았다.
function endGame() {
    gameState = "ending";
    setGameActive(false);
}

function startGame() {
    gameState = "game";
    setGameActive(true);
    playBgm("game");
    timeLeft = initialTime;
    score = 0;
    gold = INITIAL_GOLD;
    waterQuality = 70.0;
    isGameOver = false;
    fishCount = INITIAL_FISH_COUNT;
    ownedSpecialFishes = { witch: 0, ghost: 0, santa: 0, pumpkin: 0 };
    targetX = mapWidth / 2;
    targetY = mapHeight / 2;
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
    let isLarge = Math.random() < LARGE_TRASH_CHANCE;
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
        endGame();
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
        endGame();
        playBgm("ending");
        sfx.pump.pause(); sfx.pump.currentTime = 0;
        return;
    }

    if (timeLeft <= 0) {
        isGameOver = true;
        endGame();
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
    if (monsterSpawnTimer >= MONSTER_SPAWN_INTERVAL_SECONDS) {
        monsterSpawnTimer = 0;
        if (monsters.length < MAX_MONSTERS) spawnMonster();
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

// 게임 중에만 캔버스 너비를 늘리고, 시작·종료 화면은 800×600을 유지한다.
function updateResponsiveCanvas() {
    // 카메라와 제어 패널은 게임 중에만 표시한다.
    const inGame = (gameState === "game");
    document.getElementById('cameraPanel').classList.toggle('panel-hidden', !inGame || !ANY_CAM_SHOWN);
    document.getElementById('ledPanel').classList.toggle('panel-hidden', !inGame);
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

    // 오른쪽 패널은 고정 폭 사이드바를 따라 이동한다.
    const sidebarX = canvas.width - 230;
    document.getElementById('ledPanel').style.left = (sidebarX + 15) + 'px';
    document.getElementById('actuatorPanel').style.left = (sidebarX + 15) + 'px';

    // 넓은 화면에서도 호수 배경이 비지 않도록 맵 너비를 맞춘다.
    mapWidth = Math.max(MIN_MAP_WIDTH, sidebarX);
}

// ===== 브라우저 Gamepad API 버튼 입력 =====
// 버튼 번호는 상단 사용자 설정에서 변경한다.
let prevGachaButtonPressed = false;

function pollGamepadForGacha() {
    if (gameState !== "game" || activeCardShown) {
        prevGachaButtonPressed = false;
        return;
    }

    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    const pad = pads[0];
    const button = pad && pad.buttons[GACHA_GAMEPAD_BUTTON_INDEX];
    const pressed = !!(button && button.pressed);

    if (pressed && !prevGachaButtonPressed) {
        rollGachaFish();
    }
    prevGachaButtonPressed = pressed;
}

// LED 토글
let prevLedButtonPressed = false;

function pollGamepadForLed() {
    if (gameState !== "game" || activeCardShown) {
        prevLedButtonPressed = false;
        return;
    }

    const pads = navigator.getGamepads ? navigator.getGamepads() : [];
    const pad = pads[0];
    const button = pad && pad.buttons[LED_GAMEPAD_BUTTON_INDEX];
    const pressed = !!(button && button.pressed);

    if (pressed && !prevLedButtonPressed) {
        toggleLed(); // 버튼을 누르는 순간(edge)에만 1회 실행
    }
    prevLedButtonPressed = pressed;
}

// 게임 시작
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

// 메인 화면으로 돌아가기
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
    pollGamepadForLed();
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

        // /cmd_vel(조이스틱 → joy_to_cmd_node의 실제 명령)을 화면 방향(dx,dy)으로
        // 역변환한다. 게임 보트 위치와 방향은 이 명령만 사용하며 GPS와 연동하지 않는다.
        const isMoving = hasBoatMotionCommand();

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

            let len = Math.hypot(dx, dy);
            targetX = Math.max(30, Math.min(targetX + (dx / len) * BOAT_SPEED_PX, mapWidth - 30));
            targetY = Math.max(30, Math.min(targetY + (dy / len) * BOAT_SPEED_PX, mapHeight - 30));
        }

        // 사이드바(HUD)는 캔버스 우측 230px 고정, 나머지가 호수(플레이 뷰포트) 폭.
        // 캔버스가 창 크기에 맞춰 넓어지면 호수도 그만큼 더 넓게 보인다 (updateResponsiveCanvas 참고).
        const sidebarX = canvas.width - 230;
        const lakeWidth = sidebarX;

        let cameraX = Math.max(0, Math.min(targetX - lakeWidth / 2, mapWidth - lakeWidth));
        let cameraY = Math.max(0, Math.min(targetY - 400, mapHeight - 600)); // 보트를 화면 위에서 2/3 지점에 표시

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

        // 5. 보트와 수질 오로라
        let screenBoatX = targetX - cameraX;
        let screenBoatY = targetY - cameraY;

        // 오로라 색상은 실제 clarity_pct를 따르며 게임 점수용 수질과 별개다.
        let currentAuraImg = assets.green;
        let auraAlpha = 0.55;
        if (sensorWQ.clarity_pct !== null && sensorWQ.clarity_pct !== undefined) {
            if (sensorWQ.clarity_pct < 40) {
                currentAuraImg = assets.red;
                auraAlpha = 0.85;
            } else if (sensorWQ.clarity_pct < 60) {
                currentAuraImg = assets.yellow;
                auraAlpha = 0.85;
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
                ctx.globalAlpha = auraAlpha;
                let auraSize = 75;
                ctx.drawImage(tempAuraCanvas, screenBoatX - auraSize / 2, screenBoatY - auraSize / 2, auraSize, auraSize);
                ctx.restore();
            } catch (err) {
                ctx.save();
                ctx.globalAlpha = auraAlpha;
                ctx.drawImage(currentAuraImg, screenBoatX - 37, screenBoatY - 37, 75, 75);
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

        // 6. LED 이펙트 - LED가 켜진 동안만 보트 주변에 led_effect.json 애니메이션을 겹쳐 그린다.
        // ledEffectCanvas는 lottie-web이 #ledEffectHost 안에 만든 내부 canvas로,
        // updateLedUi()가 재생/정지만 토글하고 실제 그리기는 여기서 매 프레임 수행한다.
        if (ledOn === true && ledEffectCanvas) {
            const ledFxSize = 160;
            ctx.save();
            ctx.globalCompositeOperation = 'screen';
            ctx.drawImage(ledEffectCanvas, screenBoatX - ledFxSize / 2, screenBoatY - ledFxSize / 2, ledFxSize, ledFxSize);
            ctx.restore();
        }

        // 7. 우측 UI 패널 영역
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

        // 뽑기 칸 (사이드바 맨 위 칸, 퀘스트 칸보다 위) - 압축된 버튼만 넣었다. 등급표/힌트
        // 문구는 공간이 없어 뺐고, 버튼(마우스 클릭 - 클릭 핸들러 참고)과 조이스틱 Y 버튼
        // (pollGamepadForGacha) 둘 다 그대로 rollGachaFish()를 실행한다.
        // #actuatorPanel(DOM, 실측 높이 약 99px → top:288 기준 바닥이 약 387) 바로
        // 아래에 다른 구간과 같은 8px 간격만 두고 붙인다 (top=395).
        const questPanelX = sidebarX + 15;
        const gachaPanelY = 395;
        const gachaPanelH = 55;
        ctx.fillStyle = "#150d08";
        ctx.strokeStyle = "#e29578";
        ctx.lineWidth = 2;
        ctx.fillRect(questPanelX, gachaPanelY, 200, gachaPanelH);
        ctx.strokeRect(questPanelX, gachaPanelY, 200, gachaPanelH);

        ctx.fillStyle = "#ffd166";
        ctx.font = "bold 10px '맑은 고딕'";
        ctx.fillText("🎰 랜덤 물고기 뽑기", questPanelX + 100, gachaPanelY + 13);

        ctx.fillStyle = "#3a2214";
        ctx.strokeStyle = "#ffd166";
        ctx.lineWidth = 1;
        ctx.fillRect(questPanelX + 10, gachaPanelY + 18, 180, 26);
        ctx.strokeRect(questPanelX + 10, gachaPanelY + 18, 180, 26);
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 11px '맑은 고딕'";
        ctx.fillText(`✨ 뽑기 (${GACHA_COST}G) (Y) ✨`, questPanelX + 100, gachaPanelY + 35);

        // 퀘스트 안내
        const questPanelY = gachaPanelY + gachaPanelH + 5;
        const questPanelH = 600 - questPanelY;
        ctx.fillStyle = "#150d08";
        ctx.strokeStyle = "#e29578";
        ctx.lineWidth = 2;
        ctx.fillRect(questPanelX, questPanelY, 200, questPanelH);
        ctx.strokeRect(questPanelX, questPanelY, 200, questPanelH);

        ctx.textAlign = "left";
        ctx.fillStyle = "#ffd166";
        ctx.font = "bold 11px '맑은 고딕'";
        ctx.fillText("[퀘스트 1] 푸른 호수 클리어!", questPanelX + 5, questPanelY + 18);
        ctx.fillStyle = "#ffffff";
        ctx.font = "10px '맑은 고딕'";
        ctx.fillText("목표: [B]펌프 모드 변경 후", questPanelX + 5, questPanelY + 35);
        ctx.fillText("[A]눌러 펌프 작동→쓰레기 제거!", questPanelX + 5, questPanelY + 50);
        ctx.fillStyle = "#2ed573";
        ctx.fillText("보상: 친환경 점수 + 코인 획득", questPanelX + 5, questPanelY + 65);

        ctx.fillStyle = "#ffd166";
        ctx.font = "bold 11px '맑은 고딕'";
        ctx.fillText("[퀘스트 2] 동료를 찾아라!", questPanelX + 5, questPanelY + 85);
        ctx.fillStyle = "#ffffff";
        ctx.font = "10px '맑은 고딕'";
        ctx.fillText("목표: [Y]눌러 코인으로", questPanelX + 5, questPanelY + 102);
        ctx.fillText("랜덤 물고기 뽑기!", questPanelX + 5, questPanelY + 117);
        ctx.fillStyle = "#2ed573";
        ctx.fillText("보상: 물고기마다 보너스 점수", questPanelX + 5, questPanelY + 132);

        ctx.textAlign = "center";

        // 상단 타이머: 원본 이미지의 플레이트 부분만 잘라 사용한다.
        if (assets.timeBanner.complete && assets.timeBanner.naturalWidth !== 0) {
            const TIME_BANNER_SRC_X = 25, TIME_BANNER_SRC_Y = 168;
            const TIME_BANNER_SRC_W = 460, TIME_BANNER_SRC_H = 147;
            const timeBannerW = 220;
            const timeBannerH = Math.round(timeBannerW * TIME_BANNER_SRC_H / TIME_BANNER_SRC_W);
            const timeBannerX = lakeWidth / 2 - timeBannerW / 2;
            const timeBannerY = 8;
            ctx.drawImage(
                assets.timeBanner,
                TIME_BANNER_SRC_X, TIME_BANNER_SRC_Y, TIME_BANNER_SRC_W, TIME_BANNER_SRC_H,
                timeBannerX, timeBannerY, timeBannerW, timeBannerH
            );

            const timeDisplayCx = timeBannerX + timeBannerW * 0.66;
            const timeDisplayCy = timeBannerY + timeBannerH * 0.53;
            let bannerMins = String(Math.floor(timeLeft / 60)).padStart(2, '0');
            let bannerSecs = String(timeLeft % 60).padStart(2, '0');
            ctx.save();
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillStyle = "#ffcf7a";
            ctx.font = "bold 20px 'Courier New'";
            ctx.fillText(`${bannerMins}:${bannerSecs}`, timeDisplayCx, timeDisplayCy + 1);
            ctx.restore();
        }

        // 8. 좌측 상단 미니맵
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

        // 정적맵은 현재 GPS 좌표를 중심에 놓는다. 게임 보트 좌표는 이 지도에 그리지 않는다.
        if (miniMapHasGpsFix) {
            ctx.fillStyle = "#38bdf8";
            ctx.strokeStyle = "#ffffff";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.arc(80, 83.5, 4, 0, Math.PI * 2);
            ctx.fill();
            ctx.stroke();
        }

        ctx.fillStyle = miniMapHasGpsFix ? "#55ff55" : "#ffcf7a";
        ctx.font = "bold 9px '맑은 고딕'";
        ctx.fillText(miniMapHasGpsFix ? "GPS 위치" : "GPS 신호 없음", 80, 164);

        // 9. 알림 메시지 (호수 뷰포트 폭 기준으로 가로 중앙 정렬)
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

        ctx.textAlign = "center";

        // 10. 특별 물고기 영입 카드 팝업
        if (activeCardShown && activeCardKey) {
            ctx.fillStyle = "rgba(0,0,0,0.5)";
            ctx.fillRect(0, 0, lakeWidth, 520);

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
