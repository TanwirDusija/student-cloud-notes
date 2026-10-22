const API_URL = "https://student-notes-api-2409-g7aqefesf2gpevgk.eastasia-01.azurewebsites.net/api";

const uploadForm = document.getElementById("uploadForm");
const uploadMessage = document.getElementById("uploadMessage");
const listMessage = document.getElementById("listMessage");
const notesList = document.getElementById("notesList");
const uploadButton = document.getElementById("uploadButton");
const refreshButton = document.getElementById("refreshButton");
const searchInput = document.getElementById("searchInput"); // Added to grab the search bar

let allNotes = [];

// Load notes from Azure Table Storage through our backend
async function loadNotes() {
    listMessage.textContent = "Loading notes...";
    notesList.innerHTML = "";

    try {
        const response = await fetch(`${API_URL}/notes`);

        if (!response.ok) {
            throw new Error("Could not load notes");
        }

        // Read the JSON ONLY ONCE
        const data = await response.json();
        allNotes = data.notes || []; 
        
        displayNotes(allNotes);

    } catch (error) {
        listMessage.textContent = "Could not load notes. Check whether your backend is running.";
        console.error(error);
    }
}

// Render the notes to the screen
function displayNotes(notes) {
    notesList.innerHTML = ""; // Clear existing

    listMessage.textContent = notes.length === 0
        ? "No notes found."
        : `${notes.length} note(s) available`;

    notes.forEach((note) => {
        const card = document.createElement("div");
        card.className = "note-card";

        const title = document.createElement("h3");
        title.textContent = note.title || "Untitled note";

        const subject = document.createElement("p");
        subject.textContent = `Subject: ${note.subject || "Not specified"}`;

        const uploader = document.createElement("p");
        uploader.textContent = `Uploaded by: ${note.uploader || "Unknown"}`;

        const fileName = document.createElement("p");
        fileName.textContent = `File: ${note.fileName || "Unknown"}`;

        const downloadButton = document.createElement("button");
        downloadButton.textContent = "Download PDF";

        downloadButton.addEventListener("click", () => {
            downloadNote(note.noteId, note.fileName);
        });

        card.append(title, subject, uploader, fileName, downloadButton);
        notesList.appendChild(card);
    });
}

// Search functionality
if (searchInput) {
    searchInput.addEventListener("input", (e) => {
        const searchTerm = e.target.value.toLowerCase();
        
        // Filter notes by title or subject
        const filteredNotes = allNotes.filter(note => {
            const titleMatch = (note.title || "").toLowerCase().includes(searchTerm);
            const subjectMatch = (note.subject || "").toLowerCase().includes(searchTerm);
            return titleMatch || subjectMatch;
        });
        
        displayNotes(filteredNotes);
    });
}

// Upload a PDF to the backend
uploadForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const title = document.getElementById("title").value.trim();
    const subject = document.getElementById("subject").value.trim();
    const uploader = document.getElementById("uploader").value.trim();
    const file = document.getElementById("file").files[0];

    if (!file) {
        uploadMessage.textContent = "Please choose a PDF.";
        return;
    }

    if (file.type !== "application/pdf") {
        uploadMessage.textContent = "Only PDF files are allowed.";
        return;
    }

    const params = new URLSearchParams({
        title,
        subject,
        uploader,
        fileName: file.name
    });

    uploadButton.disabled = true;
    uploadMessage.textContent = "Uploading...";

    try {
        const response = await fetch(
            `${API_URL}/upload-note?${params.toString()}`,
            {
                method: "POST",
                headers: {
                    "Content-Type": "application/pdf"
                },
                body: file
            }
        );

        const result = await response.text();

        if (!response.ok) {
            throw new Error(result || "Upload failed");
        }

        uploadMessage.textContent = "Note uploaded successfully!";
        uploadForm.reset();

        await loadNotes();

    } catch (error) {
        uploadMessage.textContent = `Upload failed: ${error.message}`;
        console.error(error);
    } finally {
        uploadButton.disabled = false;
    }
});

// Download a note using its ID
async function downloadNote(noteId, fileName) {
    try {
        const response = await fetch(
            `${API_URL}/download-note/${encodeURIComponent(noteId)}`
        );

        if (!response.ok) {
            throw new Error("Download failed");
        }

        const fileBlob = await response.blob();
        const downloadUrl = URL.createObjectURL(fileBlob);

        const link = document.createElement("a");
        link.href = downloadUrl;
        link.download = fileName || "note.pdf";
        document.body.appendChild(link);
        link.click();
        link.remove();

        URL.revokeObjectURL(downloadUrl);

    } catch (error) {
        alert(`Could not download note: ${error.message}`);
        console.error(error);
    }
}

refreshButton.addEventListener("click", loadNotes);

// Load the notes when the page opens
loadNotes();