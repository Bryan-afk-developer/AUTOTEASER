/**
 * AutoTeaser - Frontend App
 * Handles PDF upload, bank detection display, and document processing.
 */

const API_BASE = "http://localhost:8001";

// ── State ──────────────────────────────────────────────────────
let currentDocId = null;

// ── DOM Elements ───────────────────────────────────────────────
const uploadZone = document.getElementById("upload-zone");
const fileInput = document.getElementById("file-input");
const resultSection = document.getElementById("result-section");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const btnProcess = document.getElementById("btn-process");
const btnDelete = document.getElementById("btn-delete");
const processSpinner = document.getElementById("process-spinner");

// Info fields
const infoFilename = document.getElementById("info-filename");
const infoPages = document.getElementById("info-pages");
const infoBank = document.getElementById("info-bank");
const infoStatus = document.getElementById("info-status");
const textPreview = document.getElementById("text-preview");
const parsedCard = document.getElementById("parsed-card");
const parsedData = document.getElementById("parsed-data");

// Toast
const toast = document.getElementById("toast");
const toastMsg = document.getElementById("toast-msg");


// ── Health Check ───────────────────────────────────────────────

async function checkHealth() {
    try {
        const res = await fetch(`${API_BASE}/api/health`);
        if (res.ok) {
            statusDot.classList.add("online");
            statusDot.classList.remove("offline");
            statusText.textContent = "Backend conectado";
        } else {
            throw new Error();
        }
    } catch {
        statusDot.classList.add("offline");
        statusDot.classList.remove("online");
        statusText.textContent = "Backend desconectado";
    }
}


// ── Toast ──────────────────────────────────────────────────────

function showToast(msg, isError = false) {
    toastMsg.textContent = msg;
    toast.classList.toggle("error", isError);
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 3000);
}


// ── Upload ─────────────────────────────────────────────────────

uploadZone.addEventListener("click", () => fileInput.click());

uploadZone.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadZone.classList.add("dragover");
});

uploadZone.addEventListener("dragleave", () => {
    uploadZone.classList.remove("dragover");
});

uploadZone.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadZone.classList.remove("dragover");
    const file = e.dataTransfer.files[0];
    if (file) uploadFile(file);
});

fileInput.addEventListener("change", (e) => {
    const file = e.target.files[0];
    if (file) uploadFile(file);
});


async function uploadFile(file) {
    if (!file.name.toLowerCase().endsWith(".pdf")) {
        showToast("Solo se aceptan archivos PDF", true);
        return;
    }

    showToast("Subiendo PDF...");

    const formData = new FormData();
    formData.append("file", file);

    try {
        const res = await fetch(`${API_BASE}/api/upload-pdf`, {
            method: "POST",
            body: formData,
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Error al subir");
        }

        const data = await res.json();
        currentDocId = data.id;

        // Show result section
        resultSection.style.display = "block";
        infoFilename.textContent = data.file_name;
        infoPages.textContent = data.page_count;
        infoBank.textContent = data.detected_bank
            ? data.detected_bank.toUpperCase()
            : "No detectado";
        infoStatus.textContent = "Subido";
        infoStatus.className = "info-value status-badge uploaded";
        textPreview.textContent = data.text_preview || "(sin texto)";

        // Enable process button only if bank was detected
        btnProcess.disabled = !data.detected_bank;

        // Hide parsed data from previous
        parsedCard.style.display = "none";

        showToast(`Banco detectado: ${data.detected_bank || "ninguno"}`);
    } catch (err) {
        showToast(err.message, true);
    }
}


// ── Process ────────────────────────────────────────────────────

btnProcess.addEventListener("click", async () => {
    if (!currentDocId) return;

    btnProcess.disabled = true;
    processSpinner.style.display = "inline-block";
    showToast("Procesando documento...");

    try {
        const res = await fetch(`${API_BASE}/api/process/${currentDocId}`, {
            method: "POST",
        });

        const data = await res.json();

        if (!res.ok) {
            throw new Error(data.detail || "Error al procesar");
        }

        infoStatus.textContent = "Procesado";
        infoStatus.className = "info-value status-badge processed";

        // Show parsed data
        parsedCard.style.display = "block";
        parsedData.textContent = JSON.stringify(data.data, null, 2);

        showToast("Documento procesado correctamente");
    } catch (err) {
        infoStatus.textContent = "Error";
        infoStatus.className = "info-value status-badge error";
        showToast(err.message, true);
    } finally {
        processSpinner.style.display = "none";
        btnProcess.disabled = false;
    }
});


// ── Delete ─────────────────────────────────────────────────────

btnDelete.addEventListener("click", async () => {
    if (!currentDocId) return;

    try {
        await fetch(`${API_BASE}/api/documents/${currentDocId}`, {
            method: "DELETE",
        });
    } catch {
        // ignore
    }

    currentDocId = null;
    resultSection.style.display = "none";
    fileInput.value = "";
    showToast("Documento eliminado");
});


// ── Init ───────────────────────────────────────────────────────

checkHealth();
setInterval(checkHealth, 10000);
