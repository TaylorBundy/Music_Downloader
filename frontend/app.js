// const API_BASE =
//   window.API_BASE || "https://music-downloader-rifz.onrender.com";

// const form = document.getElementById("downloadForm");
// const typeSelect = document.getElementById("type");
// const formatSelect = document.getElementById("format");
// const startButton = document.getElementById("startButton");
// const cancelButton = document.getElementById("cancelButton");

// const progressSection = document.getElementById("progressSection");
// const progressBar = document.getElementById("progressBar");
// const percentText = document.getElementById("percentText");
// const statusText = document.getElementById("statusText");
// const speedText = document.getElementById("speedText");
// const etaText = document.getElementById("etaText");

// const resultSection = document.getElementById("resultSection");
// const resultName = document.getElementById("resultName");
// const downloadLink = document.getElementById("downloadLink");
// const message = document.getElementById("message");

// let currentJobId = null;
// let eventSource = null;

// const formats = {
//   audio: [
//     { value: "mp3", label: "MP3" },
//     { value: "flac", label: "FLAC" },
//     { value: "ogg", label: "OGG" },
//   ],
//   video: [
//     { value: "mp4", label: "MP4" },
//     { value: "flv", label: "FLV" },
//     { value: "mov", label: "MOV" },
//   ],
// };

// function updateFormats() {
//   formatSelect.innerHTML = "";

//   formats[typeSelect.value].forEach((item) => {
//     const option = document.createElement("option");
//     option.value = item.value;
//     option.textContent = item.label;
//     formatSelect.appendChild(option);
//   });
// }

// function showMessage(text = "") {
//   message.textContent = text;
// }

// function resetProgress() {
//   progressBar.style.width = "0%";
//   percentText.textContent = "0%";
//   statusText.textContent = "Preparando...";
//   speedText.textContent = "Velocidad: —";
//   etaText.textContent = "Tiempo restante: —";
// }

// function closeEvents() {
//   if (eventSource) {
//     eventSource.close();
//     eventSource = null;
//   }
// }

// function connectProgress(jobId) {
//   closeEvents();

//   eventSource = new EventSource(
//     `${API_BASE}/progress/${encodeURIComponent(jobId)}`,
//   );

//   eventSource.onmessage = (event) => {
//     const data = JSON.parse(event.data);

//     const progress = Number(data.progress || 0);
//     progressBar.style.width = `${progress}%`;
//     percentText.textContent = `${progress.toFixed(1)}%`;

//     statusText.textContent = data.status || "Procesando...";

//     if (data.speed) {
//       speedText.textContent = `Velocidad: ${data.speed}`;
//     }

//     if (data.eta) {
//       etaText.textContent = `Tiempo restante: ${data.eta}`;
//     }

//     if (data.status === "finished") {
//       closeEvents();

//       startButton.disabled = false;
//       cancelButton.disabled = true;

//       progressBar.style.width = "100%";
//       percentText.textContent = "100%";
//       statusText.textContent = "Completado";

//       resultName.textContent = data.filename || "Archivo generado";
//       downloadLink.href = `${API_BASE}/download/${encodeURIComponent(jobId)}`;
//       downloadLink.download = data.filename || "";
//       resultSection.classList.remove("hidden");
//     }

//     if (data.status === "error") {
//       closeEvents();
//       startButton.disabled = false;
//       cancelButton.disabled = true;
//       showMessage(data.message || "Ocurrió un error.");
//     }

//     if (data.status === "cancelled") {
//       closeEvents();
//       startButton.disabled = false;
//       cancelButton.disabled = true;
//       statusText.textContent = "Cancelado";
//       showMessage("La operación fue cancelada.");
//     }
//   };

//   eventSource.onerror = () => {
//     if (currentJobId) {
//       statusText.textContent = "Conexión de progreso interrumpida";
//     }
//   };
// }

// form.addEventListener("submit", async (event) => {
//   event.preventDefault();

//   closeEvents();
//   resultSection.classList.add("hidden");
//   showMessage("");
//   resetProgress();

//   const payload = {
//     url: document.getElementById("url").value.trim(),
//     type: typeSelect.value,
//     format: formatSelect.value,
//     filename: document.getElementById("filename").value.trim(),
//     start_time: document.getElementById("startTime").value.trim(),
//     end_time: document.getElementById("endTime").value.trim(),
//     destination: document.getElementById("destination").value.trim(),
//   };

//   if (!payload.url) {
//     showMessage("Ingresá una URL.");
//     return;
//   }

//   //const timeRegex = /^\\d{1,2}:\\d{2}:\\d{2}$/;
//   const timeRegex = /^[0-9]{1,2}:[0-9]{2}:[0-9]{2}$/;

//   if (payload.start_time && !timeRegex.test(payload.start_time)) {
//     showMessage("El tiempo de inicio debe tener formato HH:MM:SS.");
//     return;
//   }

//   if (payload.end_time && !timeRegex.test(payload.end_time)) {
//     showMessage("El tiempo final debe tener formato HH:MM:SS.");
//     return;
//   }

//   if (payload.start_time && payload.end_time) {
//     const toSeconds = (value) => {
//       const parts = value.split(":").map(Number);
//       return parts[0] * 3600 + parts[1] * 60 + parts[2];
//     };

//     if (toSeconds(payload.end_time) <= toSeconds(payload.start_time)) {
//       showMessage("El tiempo final debe ser mayor que el tiempo de inicio.");
//       return;
//     }
//   }

//   startButton.disabled = true;
//   cancelButton.disabled = false;
//   progressSection.classList.remove("hidden");

//   try {
//     const response = await fetch(`${API_BASE}/download`, {
//       method: "POST",
//       headers: {
//         "Content-Type": "application/json",
//       },
//       body: JSON.stringify(payload),
//     });

//     const data = await response.json();

//     if (!response.ok) {
//       throw new Error(data.error || "No se pudo iniciar la descarga.");
//     }

//     currentJobId = data.job_id;
//     connectProgress(currentJobId);
//   } catch (error) {
//     startButton.disabled = false;
//     cancelButton.disabled = true;
//     showMessage(error.message);
//   }
// });

// cancelButton.addEventListener("click", async () => {
//   if (!currentJobId) return;

//   cancelButton.disabled = true;

//   try {
//     await fetch(`${API_BASE}/cancel/${encodeURIComponent(currentJobId)}`, {
//       method: "POST",
//     });
//   } catch {
//     showMessage("No se pudo enviar la cancelación.");
//   }
// });

// typeSelect.addEventListener("change", updateFormats);

// updateFormats();
// cancelButton.disabled = true;

// const API_BASE =
//   window.API_BASE ||
//   "https://music-downloader-rifz.onrender.com" ||
//   "https://music-downloader-1-du7y.onrender.com";

// const API_SERVERS = [
//   "https://music-downloader-rifz.onrender.com",
//   "https://music-downloader-1-du7y.onrender.com"
// ];

// let API_BASE = window.API_BASE || API_SERVERS[0];

// async function detectarServidor() {
//   if (window.API_BASE) {
//     API_BASE = window.API_BASE;
//     return API_BASE;
//   }

//   for (const servidor of API_SERVERS) {
//     try {
//       const response = await fetch(`${servidor}/health`, {
//         method: "GET"
//       });

//       if (response.ok) {
//         API_BASE = servidor;
//         return API_BASE;
//       }
//     } catch (error) {
//       console.warn(`Servidor no disponible: ${servidor}`);
//     }
//   }

//   throw new Error("No hay ningún servidor disponible.");
// }

const urlObj = new URL(window.location.toString());
const domain = urlObj.hostname;
const fullUrl = urlObj.href;
const SERVIDORES = [
  "https://music-downloader-rifz.onrender.com",
  "https://music-downloader-1-du7y.onrender.com",
];
// const servidorLocal =
//   window.location.hostname === "127.0.0.1" ||
//   window.location.hostname === "localhost";
const servidorLocal =
  window.location.protocol === "file:" ||
  window.location.hostname === "127.0.0.1" ||
  window.location.hostname === "localhost";

let API_BASE = window.API_BASE || null;
let ACTIVE_API_BASE = API_BASE;

async function comprobarServidor(servidor) {
  const controller = new AbortController();

  const timeout = setTimeout(() => {
    controller.abort();
  }, 5000);

  try {
    const response = await fetch(`${servidor}/health`, {
      signal: controller.signal,
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const data = await response.json();

    if (data.status !== "ok") {
      throw new Error("Health check inválido");
    }

    return servidor;
  } finally {
    clearTimeout(timeout);
  }
}

async function detectarServidor() {
  if (window.API_BASE) {
    API_BASE = window.API_BASE;
    return API_BASE;
  }

  API_BASE = await Promise.any(SERVIDORES.map(comprobarServidor));

  console.log("Servidor seleccionado:", API_BASE);

  return API_BASE;
}

async function detectarServidor2() {
  // Si ya fue configurado manualmente
  if (window.API_BASE) {
    API_BASE = window.API_BASE;
    return API_BASE;
  }

  for (const servidor of SERVIDORES) {
    try {
      const controller = new AbortController();

      const timeout = setTimeout(() => {
        controller.abort();
      }, 5000);

      const response = await fetch(`${servidor}/health`, {
        method: "GET",
        signal: controller.signal,
        cache: "no-store",
      });

      clearTimeout(timeout);

      if (!response.ok) {
        continue;
      }

      const data = await response.json();

      if (data.status === "ok") {
        API_BASE = servidor;

        console.log("Servidor activo:", API_BASE);

        return API_BASE;
      }
    } catch (error) {
      console.warn("Servidor no disponible:", servidor);
    }
  }

  throw new Error("No se encontró ningún servidor de Render disponible.");
}

const form = document.getElementById("downloadForm");
console.log("FORMULARIO ENCONTRADO:", form);
const typeSelect = document.getElementById("type");
const formatSelect = document.getElementById("format");
const startButton = document.getElementById("startButton");
const cancelButton = document.getElementById("cancelButton");

const progressSection = document.getElementById("progressSection");
const progressBar = document.getElementById("progressBar");
const percentText = document.getElementById("percentText");
const statusText = document.getElementById("statusText");
const speedText = document.getElementById("speedText");
const etaText = document.getElementById("etaText");

const resultSection = document.getElementById("resultSection");
const resultName = document.getElementById("resultName");
const downloadLink = document.getElementById("downloadLink");
const message = document.getElementById("message");
const cookiesFileInput = document.getElementById("cookiesFile");
const cookiesName = document.getElementById("cookiesName");
const cookieValor = document.getElementById("youtubeCookies");

let currentJobId = null;
let eventSource = null;

const formats = {
  audio: [
    { value: "mp3", label: "MP3" },
    { value: "flac", label: "FLAC" },
    { value: "ogg", label: "OGG" },
  ],
  video: [
    { value: "mp4", label: "MP4" },
    { value: "flv", label: "FLV" },
    { value: "mov", label: "MOV" },
  ],
};

function updateFormats() {
  formatSelect.innerHTML = "";

  formats[typeSelect.value].forEach((item) => {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.label;
    formatSelect.appendChild(option);
  });
}

function showMessage(text = "") {
  message.textContent = text;
}

function resetProgress() {
  progressBar.style.width = "0%";
  percentText.textContent = "0%";
  statusText.textContent = "Preparando...";
  speedText.textContent = "Velocidad: —";
  etaText.textContent = "Tiempo restante: —";
}

function closeEvents() {
  if (eventSource) {
    eventSource.close();
    eventSource = null;
  }
}

function connectProgress(jobId) {
  closeEvents();

  eventSource = new EventSource(
    `${ACTIVE_API_BASE}/progress/${encodeURIComponent(jobId)}`,
  );

  eventSource.onmessage = (event) => {
    console.log("📥 SSE RAW:", event.data);
    const data = JSON.parse(event.data);
    console.log("📦 SSE DATA:", data);
    console.log("📊 PROGRESS:", data.progress);

    const progress = Number(data.progress || 0);
    console.log("📈 PROGRESS NUMBER:", progress);
    progressBar.style.width = `${progress}%`;
    percentText.textContent = `${progress.toFixed(1)}%`;

    statusText.textContent = data.status || "Procesando...";

    if (data.speed) {
      speedText.textContent = `Velocidad: ${data.speed}`;
    }

    if (data.eta) {
      etaText.textContent = `Tiempo restante: ${data.eta}`;
    }

    if (data.status === "finished") {
      closeEvents();

      startButton.disabled = false;
      cancelButton.disabled = true;

      progressBar.style.width = "100%";
      percentText.textContent = "100%";
      statusText.textContent = "Completado";

      resultName.textContent = data.filename || "Archivo generado";
      downloadLink.href = `${ACTIVE_API_BASE}/download/${encodeURIComponent(jobId)}`;
      downloadLink.download = data.filename || "";
      resultSection.classList.remove("hidden");
    }

    if (data.status === "error") {
      closeEvents();
      startButton.disabled = false;
      cancelButton.disabled = true;
      showMessage(data.message || "Ocurrió un error.");
    }

    if (data.status === "cancelled") {
      closeEvents();
      startButton.disabled = false;
      cancelButton.disabled = true;
      statusText.textContent = "Cancelado";
      showMessage("La operación fue cancelada.");
    }
  };

  eventSource.onerror = () => {
    if (currentJobId) {
      statusText.textContent = "Conexión de progreso interrumpida";
    }
  };
}
startButton.addEventListener("click", async (event) => {
  //form.addEventListener("submit", async (event) => {
  console.log("🔥 SUBMIT DETECTADO");

  event.preventDefault();
  event.stopPropagation();

  console.log("🔥 preventDefault ejecutado");
  // event.preventDefault();
  // event.stopPropagation();

  closeEvents();
  resultSection.classList.add("hidden");
  showMessage("");
  resetProgress();

  progressSection.classList.remove("hidden");
  // ESTADO DE BOTONES
  startButton.disabled = true;
  cancelButton.disabled = false;

  const url = document.getElementById("url").value.trim();
  const startTime = document.getElementById("startTime").value.trim();
  const endTime = document.getElementById("endTime").value.trim();
  const filename = document.getElementById("filename").value.trim();
  const destination = document.getElementById("destination").value.trim();

  if (!url) {
    showMessage("Ingresá una URL.");
    return;
  }

  const timeRegex = /^[0-9]{1,2}:[0-9]{2}:[0-9]{2}$/;

  if (startTime && !timeRegex.test(startTime)) {
    showMessage("El tiempo de inicio debe tener formato HH:MM:SS.");
    return;
  }

  if (endTime && !timeRegex.test(endTime)) {
    showMessage("El tiempo final debe tener formato HH:MM:SS.");
    return;
  }

  if (startTime && endTime) {
    const toSeconds = (value) => {
      const parts = value.split(":").map(Number);
      return parts[0] * 3600 + parts[1] * 60 + parts[2];
    };

    if (toSeconds(endTime) <= toSeconds(startTime)) {
      showMessage("El tiempo final debe ser mayor que el tiempo de inicio.");
      return;
    }
  }

  const destinooo = "C:\Users\juan carlos\Music\Taylor";
  const formData = new FormData();
  formData.append("url", url);
  formData.append("type", typeSelect.value);
  formData.append("format", formatSelect.value);
  formData.append("filename", filename);
  formData.append("start_time", startTime);
  formData.append("end_time", endTime);
  formData.append("destination", destination);

  if (cookieValor.value.length > 0) {
    formData.append("cookies", cookieValor.value);
  }

  try {
    let response;
    if (servidorLocal) {
      console.log(servidorLocal);
      ACTIVE_API_BASE = "http://127.0.0.1:5000";
      //await detectarServidor();
      response = await fetch(`${ACTIVE_API_BASE}/downloadLocal`, {
        method: "POST",
        body: formData,
      });
    } else {
      ACTIVE_API_BASE = API_BASE;
      await detectarServidor();
      response = await fetch(`${ACTIVE_API_BASE}/download`, {
        method: "POST",
        body: formData,
      });
    }
    //await detectarServidor();
    // const response = await fetch(`${API_BASE}/download`, {
    //   method: "POST",
    //   body: formData,
    // });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "No se pudo iniciar la descarga.");
    }

    currentJobId = data.job_id;
    console.log("Progreso:", `${ACTIVE_API_BASE}/progress/${currentJobId}`);
    connectProgress(currentJobId);
    progressSection.classList.remove("hidden");
  } catch (error) {
    startButton.disabled = false;
    cancelButton.disabled = true;
    progressSection.classList.remove("hidden");
    showMessage(error.message);
  }
});

cancelButton.addEventListener("click", async () => {
  if (!currentJobId) return;

  cancelButton.disabled = true;

  try {
    await fetch(
      `${ACTIVE_API_BASE}/cancel/${encodeURIComponent(currentJobId)}`,
      {
        method: "POST",
      },
    );
  } catch {
    showMessage("No se pudo enviar la cancelación.");
  }
});

cookiesFileInput.addEventListener("change", () => {
  cookiesName.textContent = cookiesFileInput.files.length
    ? cookiesFileInput.files[0].name
    : "Ningún archivo seleccionado";
});

typeSelect.addEventListener("change", updateFormats);

updateFormats();
cancelButton.disabled = true;
