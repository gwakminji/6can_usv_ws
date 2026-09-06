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
      position: absolute; top: 480px; left: 585px; width: 200px; height: 120px;
      background-color: #1c100a; border: 2px solid #38bdf8; box-sizing: border-box;
      padding: 3px; display: flex; flex-direction: column; justify-content: space-between;
      z-index: 10;
  }
  .cam-box {
      width: 100%; height: 54px; background-color: #000; border: 1px solid #38bdf8;
      position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center;
  }
  .cam-title {
      position: absolute; top: 2px; left: 4px; font-size: 8px; color: #38bdf8; font-weight: bold;
      background: rgba(0, 0, 0, 0.7); padding: 1px 3px; border-radius: 2px; z-index: 2;
  }
  .cam-box img { width: 100%; height: 100%; object-fit: cover; }
  .cam-warn { font-size: 8px; color: #fdd; text-align: center; padding: 0 4px; }

  #actuatorPanel {
      /* 위쪽 미니맵(canvas 내부 15,15 위치에 130x137로 그려짐)과 가로폭을 맞췄다 */
      position: absolute; top: 190px; left: 18px; width: 130px; box-sizing: border-box;
      background-color: #150d08; border: 2px solid #e29578; padding: 6px; font-size: 11px;
      z-index: 10;
  }
  #actuatorPanel .title { color: #ffd166; font-weight: bold; margin-bottom: 4px; }
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
</style>
</head>
<body>
<div id="gameContainer">
    <div id="gpsBanner">⚠ GPS 신호 없음 (마지막 위치 유지 중)</div>
    <canvas id="gameCanvas" width="800" height="600"></canvas>

    <div id="cameraPanel">
        <div class="cam-box">
            <span class="cam-title">📷 수면 (Surface)</span>
            <img id="surfaceCam" alt="수면 카메라 연결 중..." onerror="this.style.opacity=0.3">
        </div>
        <div class="cam-box">
            <span class="cam-title">🌊 수중 (Underwater)</span>
            <img id="underwaterCam" alt="수중 카메라 연결 중..." onerror="this.style.opacity=0.3">
        </div>
    </div>

    <div id="actuatorPanel">
        <div class="title">펌프 제어</div>
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
        <div style="margin-top:6px">LED: <input type="color" id="ledColor" value="#00ff00" onchange="setLed()"> 실제: <span id="ledStateActual">-</span></div>
    </div>
</div>

<script>
// --- [카메라 스트림] B1 보드의 camera_streaming 패키지(http_video_server)가 MJPEG를
// 직접 서빙한다 - GCS 자신이 아니라 B1 보드 위에서 도는 서버라 GCS의 location.hostname으로
// 폴백하면 안 된다(폴백하면 GCS 자신의 8000번을 찍어서 조용히 검은 화면이 된다). 포트는
// camera_streaming 쪽 고정값(8000). 호스트는 gui_main_node.py의 camera_host 파라미터
// (gcs.launch.py camera_host 인자 또는 config/gcs_params.yaml)로 주입된다. 값이 비어있으면
// 폴백 없이 화면에 설정 안내를 띄운다 - 잘못된 주소로 붙는 것보다 낫다.
const CAMERA_PORT = 8000;
const cameraHost = "__CAMERA_HOST__";
if (cameraHost) {
    document.getElementById('surfaceCam').src =
        `http://${cameraHost}:${CAMERA_PORT}/stream?topic=/camera/surface/image_raw`;
    document.getElementById('underwaterCam').src =
        `http://${cameraHost}:${CAMERA_PORT}/stream?topic=/camera/underwater/image_raw`;
} else {
    document.querySelectorAll('#cameraPanel .cam-box').forEach((box) => {
        const warn = document.createElement('div');
        warn.className = 'cam-warn';
        warn.textContent = 'camera_host 미설정 (gcs_params.yaml)';
        box.appendChild(warn);
    });
}

// --- [펌프] 조종은 조이스틱 하나로만 하므로 펌프도 joy_to_cmd_node가 조이스틱 버튼으로
// 직접 /actuator/pump_cmd를 발행한다. 이 화면은 그 상태를 표시만 한다(버튼 없음). ---

// --- [LED] 아직 조이스틱에 버튼을 안 배정해서 여기 색상 피커로 /api/led에 POST ---
function setLed() {
    const hex = document.getElementById('ledColor').value;
    const r = parseInt(hex.slice(1, 3), 16) / 255;
    const g = parseInt(hex.slice(3, 5), 16) / 255;
    const b = parseInt(hex.slice(5, 7), 16) / 255;
    fetch('/api/led', {
        method: 'POST', headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({r, g, b})
    });
}

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

        if (s.led_state) {
            const toHex = (v) => Math.round(v * 255).toString(16).padStart(2, '0');
            document.getElementById('ledStateActual').textContent =
                `#${toHex(s.led_state.r)}${toHex(s.led_state.g)}${toHex(s.led_state.b)}`;
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
    red: new Image()
};

// 이미지 파일명 매칭 설정
assets.lake.src = "lake.png";
assets.ending.src = "ending.png";
assets.mainstart.src = "mainstart.jpg";
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

// 게임 상태 관리 ("main" 또는 "game" 또는 "ending")
let gameState = "main";

// 게임 변수들
let initialTime = 90;
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
let notificationText = "";
let notificationTimer = null;

// 뽑기 등급표: chance는 100 기준 당첨 확률(%) - 점수(score_val)가 높은 물고기일수록
// 낮게 잡아서 좋은 물고기일수록 잘 안 나오게 한다. 4개 합은 100이어야 함.
const specialFishTemplates = {
    witch: { name: "WITCH FISH", kor_name: "마녀 피쉬", rarity: "일반", chance: 55, score_val: 15, desc: "쓰레기 패널티 30% 완화 🎩" },
    ghost: { name: "GHOST LOBSTER", kor_name: "유령 가재", rarity: "희귀", chance: 28, score_val: 25, desc: "10초마다 +15G 생산 👻" },
    santa: { name: "SANTA GOLDFISH", kor_name: "산타 금붕어", rarity: "영웅", chance: 13, score_val: 35, desc: "적정 수질 시 점수 1.4배 🎅" },
    pumpkin: { name: "PUMPKIN FISH", kor_name: "호박 왕관피쉬", rarity: "전설", chance: 4, score_val: 50, desc: "초당 기본 점수 든든하게 +50점 👑" }
};
const GACHA_COST = 150;

// 마우스 클릭 이벤트 처리
canvas.addEventListener("click", (e) => {
    const rect = canvas.getBoundingClientRect();
    // 화면 확대(fitGameContainer의 transform: scale)로 캔버스의 실제 렌더링 크기가
    // 내부 해상도(800x600)와 달라지므로, 클릭 좌표를 내부 해상도 기준으로 환산한다.
    const x = (e.clientX - rect.left) * (canvas.width / rect.width);
    const y = (e.clientY - rect.top) * (canvas.height / rect.height);

    if (gameState === "main") {
        if (x >= 300 && x <= 500 && y >= 190 && y <= 260) {
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
        if (x >= sidebarX + 25 && x <= sidebarX + 205 && y >= 290 && y <= 326) {
            rollGachaFish();
        }
    } else if (gameState === "ending") {
        if (x >= 260 && x <= 540 && y >= 480 && y <= 540) {
            gameState = "main";
        }
    }
});

function startGame() {
    gameState = "game";
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
    let garbageImgs = [assets.garbage1, assets.garbage2, assets.garbageSmall1, assets.garbageSmall2, assets.garbageSmall3];
    let chosenImg = garbageImgs[Math.floor(Math.random() * garbageImgs.length)];
    monsters.push({
        x: Math.random() * (mapWidth - 200) + 100,
        y: Math.random() * (mapHeight - 200) + 100,
        photo: chosenImg,
        hp: 3
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
    setTimeout(() => {
        hideFishCardPopup();
    }, 1500);
}

function hideFishCardPopup() {
    activeCardShown = false;
}

// 조이스틱 버튼 하나로 실행되는 랜덤 뽑기. 4개 물고기 중 하나를 chance(%) 가중치로
// 추첨한다 - 값이 좋은 물고기(pumpkin 등)일수록 chance가 낮게 설정되어 있어 잘 안 나온다.
function rollGachaFish() {
    if (activeCardShown) return; // 카드 팝업이 떠 있는 동안은 중복 뽑기 방지

    if (gold < GACHA_COST) {
        showInGameMessage(`❌ 골드가 부족합니다! (필요: ${GACHA_COST}G)`);
        return;
    }
    gold -= GACHA_COST;

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
        return;
    }

    if (timeLeft <= 0) {
        isGameOver = true;
        alert(`TIME OVER ⏳\n최종 점수: ${score}점`);
        gameState = "main";
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
    if (monsterSpawnTimer >= 6) {
        monsterSpawnTimer = 0;
        if (monsters.length < 15) spawnMonster();
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
    // #cameraPanel은 DOM 오버레이라 캔버스 좌표와 별개로 위치를 직접 맞춰줘야 한다.
    const sidebarX = canvas.width - 230;
    document.getElementById('cameraPanel').style.left = (sidebarX + 15) + 'px';

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

// --- [조이스틱 게임 시작 버튼] 메인 화면에서 마우스로 "게임 화면 시작"을 누르는 대신
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

let animTimer = 0;
function mainLoop() {
    pollGamepadForGacha();
    pollGamepadForStart();
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

        ctx.fillStyle = "#3a2214";
        ctx.strokeStyle = "#e29578";
        ctx.lineWidth = 3;
        ctx.fillRect(300, 190, 200, 70);
        ctx.strokeRect(300, 190, 200, 70);

        ctx.fillStyle = "white";
        ctx.font = "bold 16px '맑은 고딕'";
        ctx.fillText("게임 화면 시작", 400, 230);
        ctx.textAlign = "left";

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
            let mx = m.x - cameraX;
            let my = m.y - cameraY;
            if (mx >= -30 && mx <= lakeWidth + 30 && my >= -30 && my <= 630) {
                if (m.photo.complete && m.photo.naturalWidth !== 0) {
                    ctx.drawImage(m.photo, mx - 14, my - 14, 28, 28);
                } else {
                    ctx.fillStyle = "#888";
                    ctx.fillRect(mx - 14, my - 14, 28, 28);
                }
            }

            if (isPumping) {
                let dist = Math.hypot(beamWorldX - m.x, beamWorldY - m.y);
                if (dist < 75) {
                    m.hp -= 1;
                    if (m.hp <= 0) {
                        let idx = monsters.indexOf(m);
                        if (idx > -1) monsters.splice(idx, 1);
                        let reward = Math.floor(Math.random() * 16) + 15;
                        gold += reward;
                        showInGameMessage(`✨ 쓰레기 수거 성공! (+${reward}G)`);
                    }
                }
            }
        });

        // 4. 물대포 이펙트
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
        ctx.fillStyle = "#150d08";
        ctx.strokeStyle = "#e29578";
        ctx.lineWidth = 2;
        ctx.fillRect(sidebarX + 15, 260, 200, 210);
        ctx.strokeRect(sidebarX + 15, 260, 200, 210);

        ctx.fillStyle = "#ffd166";
        ctx.font = "bold 11px '맑은 고딕'";
        ctx.fillText("🎰 랜덤 물고기 뽑기", sidebarX + 115, 280);

        // 뽑기 버튼 - 마우스 클릭(클릭 핸들러 참고) 또는 조이스틱 버튼(pollGamepadForGacha)으로 실행
        ctx.fillStyle = "#3a2214";
        ctx.strokeStyle = "#ffd166";
        ctx.lineWidth = 1;
        ctx.fillRect(sidebarX + 25, 290, 180, 36);
        ctx.strokeRect(sidebarX + 25, 290, 180, 36);
        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 12px '맑은 고딕'";
        ctx.fillText(`✨ 뽑기 (${GACHA_COST}G) ✨`, sidebarX + 115, 312);

        ctx.fillStyle = "#a5a5a5";
        ctx.font = "9px '맑은 고딕'";
        ctx.fillText("(조이스틱 X 버튼으로도 실행 가능)", sidebarX + 115, 340);

        ctx.fillStyle = "#ffd166";
        ctx.font = "bold 10px '맑은 고딕'";
        ctx.fillText("[ 등급표 ]", sidebarX + 115, 358);

        let rarityRows = ["witch", "ghost", "santa", "pumpkin"].map((key, i) => ({
            key, y: 374 + i * 18
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

        // 9. 특별 물고기 영입 카드 팝업
        if (activeCardShown && activeCardKey) {
            ctx.fillStyle = "rgba(0,0,0,0.5)";
            ctx.fillRect(0, 0, lakeWidth, 600);

            const cardX = lakeCenterX - 110;
            ctx.fillStyle = "#110a05";
            ctx.strokeStyle = "#e29578";
            ctx.lineWidth = 3;
            ctx.fillRect(cardX, 105, 220, 390);
            ctx.strokeRect(cardX, 105, 220, 390);

            ctx.fillStyle = "#ffd166";
            ctx.font = "bold 10px 'Courier New'";
            ctx.fillText("★  XVII  ★", lakeCenterX, 125);

            ctx.fillStyle = "#ffffff";
            ctx.font = "bold 12px 'Courier New'";
            ctx.fillText(specialFishTemplates[activeCardKey].name, lakeCenterX, 150);

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

            ctx.fillStyle = "#f43f5e";
            ctx.font = "italic 9px '맑은 고딕'";
            ctx.fillText("- 1.5초 후 자동 닫힘 -", lakeCenterX, 445);
        }

        ctx.textAlign = "left";

    } else if (gameState === "ending") {
        if (assets.ending.complete && assets.ending.naturalWidth !== 0) {
            ctx.drawImage(assets.ending, 0, 0, 800, 600);
        } else {
            ctx.fillStyle = "#1890ff";
            ctx.fillRect(0, 0, 800, 600);
        }

        let elapsed = initialTime - timeLeft;
        let mMin = Math.floor(elapsed / 60);
        let mSec = elapsed % 60;
        let timeStr = mMin > 0 ? `${mMin}분 ${mSec}초` : `${mSec}초`;

        ctx.fillStyle = "#1c100a";
        ctx.strokeStyle = "#ffd166";
        ctx.lineWidth = 3;
        ctx.fillRect(230, 320, 340, 120);
        ctx.strokeRect(230, 320, 340, 120);

        ctx.textAlign = "center";
        ctx.fillStyle = "#ffd166";
        ctx.font = "bold 18px '맑은 고딕'";
        ctx.fillText(`🏆 최종 점수 : ${score.toLocaleString()}점`, 400, 365);

        ctx.fillStyle = "#4cc9f0";
        ctx.fillText(`⏱️ 소요 시간 : ${timeStr}`, 400, 405);

        ctx.fillStyle = "#1e293b";
        ctx.strokeStyle = "#38bdf8";
        ctx.lineWidth = 3;
        ctx.fillRect(260, 480, 280, 60);
        ctx.strokeRect(260, 480, 280, 60);

        ctx.fillStyle = "#ffffff";
        ctx.font = "bold 15px '맑은 고딕'";
        ctx.fillText("🏠 메인 화면으로 돌아가기", 400, 517);
        ctx.textAlign = "left";
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