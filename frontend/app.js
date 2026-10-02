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

const API_BASE =
  window.API_BASE || "https://music-downloader-rifz.onrender.com";

const form = document.getElementById("downloadForm");
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
    `${API_BASE}/progress/${encodeURIComponent(jobId)}`,
  );

  eventSource.onmessage = (event) => {
    const data = JSON.parse(event.data);

    const progress = Number(data.progress || 0);
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
      downloadLink.href = `${API_BASE}/download/${encodeURIComponent(jobId)}`;
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

form.addEventListener("submit", async (event) => {
  event.preventDefault();

  closeEvents();
  resultSection.classList.add("hidden");
  showMessage("");
  resetProgress();

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

  const formData = new FormData();
  formData.append("url", url);
  formData.append("type", typeSelect.value);
  formData.append("format", formatSelect.value);
  formData.append("filename", filename);
  formData.append("start_time", startTime);
  formData.append("end_time", endTime);
  formData.append("destination", destination);

  if (cookieValor.value.length > 0) {
    console.log("Cookies file input:", cookieValor.value);
    formData.append("cookies", cookieValor.value);
  }
  console.log([...formData.values()]);

  try {
    const response = await fetch(`${API_BASE}/download`, {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "No se pudo iniciar la descarga.");
    }

    currentJobId = data.job_id;
    connectProgress(currentJobId);
  } catch (error) {
    startButton.disabled = false;
    cancelButton.disabled = true;
    showMessage(error.message);
  }
});

cancelButton.addEventListener("click", async () => {
  if (!currentJobId) return;

  cancelButton.disabled = true;

  try {
    await fetch(`${API_BASE}/cancel/${encodeURIComponent(currentJobId)}`, {
      method: "POST",
    });
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
