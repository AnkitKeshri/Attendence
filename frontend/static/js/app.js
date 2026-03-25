const video = document.getElementById('video');
const overlay = document.getElementById('overlay');
const ctx = overlay.getContext('2d');

const startCameraBtn = document.getElementById('startCameraBtn');
const stopCameraBtn = document.getElementById('stopCameraBtn');
const markAttendanceBtn = document.getElementById('markAttendanceBtn');
const refreshAttendanceBtn = document.getElementById('refreshAttendanceBtn');
const studentForm = document.getElementById('studentForm');

const qrStatus = document.getElementById('qrStatus');
const faceStatus = document.getElementById('faceStatus');
const attendanceStatus = document.getElementById('attendanceStatus');
const systemMessage = document.getElementById('systemMessage');
const registrationMessage = document.getElementById('registrationMessage');

let stream;
let token = localStorage.getItem('attendance_token') || crypto.randomUUID();
localStorage.setItem('attendance_token', token);
let loopHandle = null;
let busy = false;

function setBadge(el, label, state = 'idle') {
  el.textContent = label;
  el.className = `badge ${state}`;
}

function showMessage(message, isError = false) {
  const time = new Date().toLocaleTimeString();
  systemMessage.textContent = `[${time}] ${message}`;
  systemMessage.style.color = isError ? '#ff9eb0' : '#b8c8eb';
}

function showRegistrationMessage(message, isError = false) {
  registrationMessage.textContent = message;
  registrationMessage.style.color = isError ? '#ff9eb0' : '#7cf1be';
}

async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 640 }, height: { ideal: 480 } },
      audio: false
    });
    video.srcObject = stream;
    await video.play();
    overlay.width = video.videoWidth;
    overlay.height = video.videoHeight;
    runLoop();
    showMessage('Camera started. Keep QR and face inside the frame.');
  } catch (err) {
    showMessage(`Camera error: ${err.message}`, true);
  }
}

function stopCamera() {
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
  }
  stream = null;

  if (loopHandle) {
    clearInterval(loopHandle);
    loopHandle = null;
  }

  ctx.clearRect(0, 0, overlay.width, overlay.height);
  setBadge(qrStatus, 'QR: Waiting', 'idle');
  setBadge(faceStatus, 'Face: Waiting', 'idle');
  showMessage('Camera stopped.');
}

function grabFrameBase64() {
  const canvas = document.createElement('canvas');
  canvas.width = video.videoWidth;
  canvas.height = video.videoHeight;
  const c = canvas.getContext('2d');
  c.drawImage(video, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL('image/jpeg', 0.72);
}

async function apiPost(path, body) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Client-Token': token },
    body: JSON.stringify(body)
  });
  return response.json();
}

function drawFaces(faces) {
  ctx.clearRect(0, 0, overlay.width, overlay.height);
  ctx.strokeStyle = '#5f8bff';
  ctx.lineWidth = 2;
  faces.forEach((f) => {
    ctx.strokeRect(f.x, f.y, f.w, f.h);
  });
}

function updateQrStatus(qrData) {
  if (qrData.ok) {
    setBadge(qrStatus, `QR: Verified (${qrData.student.id})`, 'ok');
  } else if (qrData.message === 'QR not registered') {
    setBadge(qrStatus, 'QR: Invalid', 'error');
  } else {
    setBadge(qrStatus, 'QR: Waiting', 'idle');
  }
}

function updateFaceStatus(faceData) {
  if (faceData.face_detected && faceData.motion_recent) {
    setBadge(faceStatus, 'Face: Detected + Live', 'ok');
  } else if (faceData.face_detected) {
    setBadge(faceStatus, 'Face: Detected (No Motion)', 'warn');
  } else {
    setBadge(faceStatus, 'Face: Not Found', 'error');
  }
}

function runLoop() {
  if (loopHandle) {
    clearInterval(loopHandle);
  }

  loopHandle = setInterval(async () => {
    if (!stream || busy || video.videoWidth === 0) return;
    busy = true;

    const image = grabFrameBase64();

    try {
      const [qrData, faceData] = await Promise.all([
        apiPost('/scan_qr', { image }),
        apiPost('/detect_face', { image })
      ]);

      token = qrData.token || faceData.token || token;
      localStorage.setItem('attendance_token', token);

      updateQrStatus(qrData);
      updateFaceStatus(faceData);
      drawFaces(faceData.faces || []);
      showMessage(`${qrData.message || ''} ${faceData.message || ''}`.trim());
    } catch (err) {
      showMessage(`Live scan failed: ${err.message}`, true);
    } finally {
      busy = false;
    }
  }, 950);
}

async function markAttendance() {
  try {
    const data = await apiPost('/mark_attendance', {});
    if (data.ok) {
      setBadge(attendanceStatus, 'Attendance: Marked', 'ok');
      showMessage(`${data.message} for ${data.student.name}`);
      loadAttendance();
    } else {
      setBadge(attendanceStatus, 'Attendance: Failed', 'error');
      showMessage(data.message, true);
    }
  } catch (err) {
    setBadge(attendanceStatus, 'Attendance: Error', 'error');
    showMessage(`Failed to mark attendance: ${err.message}`, true);
  }
}

async function registerStudent(e) {
  e.preventDefault();
  const id = document.getElementById('studentId').value.trim();
  const name = document.getElementById('studentName').value.trim();

  try {
    const data = await apiPost('/students', { id, name });
    if (data.ok) {
      showRegistrationMessage(`Student created. QR saved as ${id}.png`);
      studentForm.reset();
    } else {
      showRegistrationMessage(data.message, true);
    }
  } catch (err) {
    showRegistrationMessage(err.message, true);
  }
}

async function loadAttendance() {
  const tableBody = document.querySelector('#attendanceTable tbody');
  tableBody.innerHTML = '';

  try {
    const res = await fetch('/get_attendance');
    const data = await res.json();

    if (!data.attendance.length) {
      const tr = document.createElement('tr');
      tr.innerHTML = '<td colspan="5">No attendance marked yet.</td>';
      tableBody.appendChild(tr);
      return;
    }

    data.attendance.forEach((row) => {
      const tr = document.createElement('tr');
      tr.innerHTML = `<td>${row.student_id}</td><td>${row.name}</td><td>${row.date}</td><td>${row.time}</td><td>${row.status}</td>`;
      tableBody.appendChild(tr);
    });
  } catch (err) {
    showMessage(`Could not load attendance: ${err.message}`, true);
  }
}

startCameraBtn.addEventListener('click', startCamera);
stopCameraBtn.addEventListener('click', stopCamera);
markAttendanceBtn.addEventListener('click', markAttendance);
refreshAttendanceBtn.addEventListener('click', loadAttendance);
studentForm.addEventListener('submit', registerStudent);
window.addEventListener('load', loadAttendance);
