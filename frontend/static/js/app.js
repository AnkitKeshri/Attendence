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
  systemMessage.textContent = message;
  systemMessage.style.color = isError ? '#b00020' : '#152238';
}

async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment', width: { ideal: 640 }, height: { ideal: 480 } }, audio: false });
    video.srcObject = stream;
    await video.play();
    overlay.width = video.videoWidth;
    overlay.height = video.videoHeight;
    runLoop();
    showMessage('Camera started. Please show QR and face clearly.');
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
  }
  ctx.clearRect(0, 0, overlay.width, overlay.height);
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
  ctx.strokeStyle = '#2f6dfc';
  ctx.lineWidth = 2;
  faces.forEach((f) => {
    ctx.strokeRect(f.x, f.y, f.w, f.h);
  });
}

async function runLoop() {
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

      if (qrData.ok) {
        setBadge(qrStatus, `QR: Verified (${qrData.student.id})`, 'ok');
      } else {
        setBadge(qrStatus, 'QR: Waiting', 'idle');
      }

      if (faceData.face_detected && faceData.motion_recent) {
        setBadge(faceStatus, 'Face: Detected + Live', 'ok');
      } else if (faceData.face_detected) {
        setBadge(faceStatus, 'Face: Detected (No Motion)', 'warn');
      } else {
        setBadge(faceStatus, 'Face: Not Found', 'error');
      }

      drawFaces(faceData.faces || []);
      showMessage(`${qrData.message || ''} ${faceData.message || ''}`.trim());
    } catch (err) {
      showMessage(`Live scan failed: ${err.message}`, true);
    } finally {
      busy = false;
    }
  }, 1000);
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
      registrationMessage.style.color = '#0a8f3f';
      registrationMessage.textContent = `Student created. QR saved as ${id}.png`; 
      studentForm.reset();
    } else {
      registrationMessage.style.color = '#b00020';
      registrationMessage.textContent = data.message;
    }
  } catch (err) {
    registrationMessage.style.color = '#b00020';
    registrationMessage.textContent = err.message;
  }
}

async function loadAttendance() {
  const tableBody = document.querySelector('#attendanceTable tbody');
  tableBody.innerHTML = '';

  const res = await fetch('/get_attendance');
  const data = await res.json();
  data.attendance.forEach((row) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${row.student_id}</td><td>${row.name}</td><td>${row.date}</td><td>${row.time}</td><td>${row.status}</td>`;
    tableBody.appendChild(tr);
  });
}

startCameraBtn.addEventListener('click', startCamera);
stopCameraBtn.addEventListener('click', stopCamera);
markAttendanceBtn.addEventListener('click', markAttendance);
refreshAttendanceBtn.addEventListener('click', loadAttendance);
studentForm.addEventListener('submit', registerStudent);
window.addEventListener('load', loadAttendance);
