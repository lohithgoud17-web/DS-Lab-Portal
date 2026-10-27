/**
 * DS LAB PORTAL - Frontend JavaScript
 * Handles Navigation, Profile ID Card modal, Dynamic Search,
 * Module Accordions, Experiment Management, and PDF operations.
 */

document.addEventListener("DOMContentLoaded", () => {
  initNavigation();
  initProfileModal();
  initModuleInteractions();
  initLabExecution();
  initToasts();
});

/* --------------------------------------------------------------------------
   Navigation & Hamburger
   -------------------------------------------------------------------------- */
function initNavigation() {
  const burger = document.getElementById("dslBurger");
  const nav = document.getElementById("dslNav");

  if (burger && nav) {
    burger.addEventListener("click", () => {
      const isOpen = nav.classList.toggle("is-open");
      burger.setAttribute("aria-expanded", String(isOpen));
    });

    document.addEventListener("click", (e) => {
      if (!nav.contains(e.target) && !burger.contains(e.target)) {
        nav.classList.remove("is-open");
        burger.setAttribute("aria-expanded", "false");
      }
    });
  }
}

/* --------------------------------------------------------------------------
   Student Profile / ID Card Editing
   -------------------------------------------------------------------------- */
function initProfileModal() {
  const openBtns = document.querySelectorAll("[data-open-profile]");
  const modal = document.getElementById("profileModal");
  const form = document.getElementById("profileForm");
  const photoInput = document.getElementById("profilePhotoInput");
  const photoPreview = document.getElementById("profilePhotoPreview");

  if (!modal || !form) return;

  openBtns.forEach((btn) => {
    btn.addEventListener("click", () => {
      openModal(modal);
      fetchProfileData();
    });
  });

  // Handle photo preview
  if (photoInput && photoPreview) {
    photoInput.addEventListener("change", () => {
      const file = photoInput.files[0];
      if (file && file.type.startsWith("image/")) {
        const reader = new FileReader();
        reader.onload = (e) => {
          photoPreview.src = e.target.result;
        };
        reader.readAsDataURL(file);
      }
    });
  }

  // Handle form submission
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const submitBtn = form.querySelector('button[type="submit"]');
    submitBtn.disabled = true;
    submitBtn.textContent = "Saving...";

    try {
      // 1. Upload photo if selected
      let photoUrl = null;
      if (photoInput && photoInput.files[0]) {
        const formData = new FormData();
        formData.append("photo", photoInput.files[0]);
        const photoRes = await fetch("/api/profile/photo", {
          method: "POST",
          body: formData,
        });
        if (photoRes.ok) {
          const pData = await photoRes.json();
          photoUrl = pData.photo_url;
        }
      }

      // 2. Update profile fields
      const payload = {
        name: document.getElementById("profName")?.value || "",
        register_no: document.getElementById("profRegister")?.value || "",
        section: document.getElementById("profSection")?.value || "",
        branch: document.getElementById("profBranch")?.value || "",
        faculty_name: document.getElementById("profFaculty")?.value || "",
        github_url: document.getElementById("profGithub")?.value || "",
      };

      if (photoUrl) {
        payload.photo_url = photoUrl;
      }

      const res = await fetch("/api/profile", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) throw new Error("Could not update profile.");
      const updated = await res.json();

      updateProfileDOM(updated);
      closeModal(modal);
      showToast("Student Profile updated successfully.");
    } catch (err) {
      showToast(err.message, true);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Save Changes";
    }
  });
}

async function fetchProfileData() {
  try {
    const res = await fetch("/api/profile");
    if (!res.ok) return;
    const data = await res.json();

    const nameInput = document.getElementById("profName");
    const regInput = document.getElementById("profRegister");
    const secInput = document.getElementById("profSection");
    const branchInput = document.getElementById("profBranch");
    const facInput = document.getElementById("profFaculty");
    const gitInput = document.getElementById("profGithub");
    const preview = document.getElementById("profilePhotoPreview");

    if (nameInput) nameInput.value = data.name || "";
    if (regInput) regInput.value = data.register_no || "";
    if (secInput) secInput.value = data.section || "";
    if (branchInput) branchInput.value = data.branch || "";
    if (facInput) facInput.value = data.faculty_name || "";
    if (gitInput) gitInput.value = data.github_url || "";
    if (preview && data.photo_url) preview.src = data.photo_url;
  } catch (err) {
    console.error("Error fetching profile:", err);
  }
}

function updateProfileDOM(data) {
  // Update header avatar & name
  const headerName = document.querySelector(".dsl-profile-name");
  const headerAvatar = document.querySelector(".dsl-profile-avatar");
  if (headerName) headerName.textContent = data.name || "Student";
  if (headerAvatar && data.photo_url) headerAvatar.src = data.photo_url;

  // Update Home ID card if present
  const idPhoto = document.getElementById("homeIdPhoto");
  const idName = document.getElementById("homeIdName");
  const idRoll = document.getElementById("homeIdRoll");
  const idSection = document.getElementById("homeIdSection");
  const idBranch = document.getElementById("homeIdBranch");
  const idFaculty = document.getElementById("homeIdFaculty");
  const idGithub = document.getElementById("homeIdGithub");

  if (idPhoto && data.photo_url) idPhoto.src = data.photo_url;
  if (idName) idName.textContent = data.name || "Not specified";
  if (idRoll) idRoll.textContent = data.register_no || "Not specified";
  if (idSection) idSection.textContent = data.section || "Not specified";
  if (idBranch) idBranch.textContent = data.branch || "Not specified";
  if (idFaculty) idFaculty.textContent = data.faculty_name || "Not specified";
  if (idGithub) {
    if (data.github_url) {
      idGithub.innerHTML = `<a href="${data.github_url}" target="_blank" rel="noopener noreferrer" class="id-card__link">View Repository &rarr;</a>`;
    } else {
      idGithub.textContent = "Not added";
    }
  }
}

/* --------------------------------------------------------------------------
   Modules Section: Accordion & Dynamic Real-time Search
   -------------------------------------------------------------------------- */
function initModuleInteractions() {
  const moduleCards = document.querySelectorAll(".module-card");
  const searchInput = document.getElementById("moduleSearch");

  // Accordion Toggle
  moduleCards.forEach((card) => {
    const header = card.querySelector(".module-card__header");
    if (!header) return;

    header.addEventListener("click", () => {
      card.classList.toggle("is-expanded");
    });
  });

  // Dynamic Search Filter
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      const query = searchInput.value.trim().toLowerCase();

      moduleCards.forEach((card) => {
        const title = card.querySelector(".module-card__title")?.textContent.toLowerCase() || "";
        const tag = card.querySelector(".module-card__tag")?.textContent.toLowerCase() || "";
        const subtopicItems = card.querySelectorAll(".subtopic-item");

        let hasMatchingSubtopic = false;

        subtopicItems.forEach((sub) => {
          const subTitle = sub.querySelector(".subtopic-item__title")?.textContent.toLowerCase() || "";
          const subDesc = sub.querySelector(".subtopic-item__desc")?.textContent.toLowerCase() || "";

          if (query === "" || subTitle.includes(query) || subDesc.includes(query)) {
            sub.style.display = "flex";
            hasMatchingSubtopic = true;
          } else {
            sub.style.display = "none";
          }
        });

        const moduleMatches = title.includes(query) || tag.includes(query);

        if (query === "") {
          card.style.display = "block";
          subtopicItems.forEach((sub) => (sub.style.display = "flex"));
        } else if (moduleMatches || hasMatchingSubtopic) {
          card.style.display = "block";
          card.classList.add("is-expanded"); // Expand to show matches
        } else {
          card.style.display = "none";
        }
      });
    });
  }

  // Add Topic Modal Interactions
  const openTopicBtn = document.getElementById("openAddTopicBtn");
  const topicModal = document.getElementById("addTopicModal");
  const topicForm = document.getElementById("addTopicForm");

  if (openTopicBtn && topicModal) {
    openTopicBtn.addEventListener("click", () => {
      topicForm.reset();
      openModal(topicModal);
    });
  }

  if (topicForm) {
    topicForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const saveBtn = document.getElementById("saveTopicBtn");
      saveBtn.disabled = true;
      saveBtn.textContent = "Uploading & Saving...";

      const formData = new FormData(topicForm);
      try {
        const res = await fetch("/api/modules/add-topic", {
          method: "POST",
          body: formData,
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.error || "Failed to add topic.");
        }

        showToast("New topic and PDF uploaded successfully!");
        closeModal(topicModal);
        setTimeout(() => location.reload(), 400);
      } catch (err) {
        showToast(err.message, true);
        saveBtn.disabled = false;
        saveBtn.textContent = "Upload & Save Topic";
      }
    });
  }
}

// Global helper to open Add Topic for a specific module
window.openAddTopicForModule = function(modId, modNumber) {
  const modal = document.getElementById("addTopicModal");
  const select = document.getElementById("topicModuleSelect");
  const form = document.getElementById("addTopicForm");
  if (modal && select) {
    if (form) form.reset();
    select.value = modId;
    openModal(modal);
  }
};
function initLabExecution() {
  const searchInput = document.getElementById("experimentSearch");
  const addBtn = document.getElementById("openAddExpBtn");
  const modal = document.getElementById("experimentModal");
  const form = document.getElementById("experimentForm");
  const coverInput = document.getElementById("expCoverInput");
  const coverPreview = document.getElementById("expCoverPreview");
  const addSubBtn = document.getElementById("addSubExpBtn");
  const subsContainer = document.getElementById("subExperimentsContainer");

  // Dynamic Experiment Search
  if (searchInput) {
    searchInput.addEventListener("input", () => {
      const query = searchInput.value.trim().toLowerCase();
      const expCards = document.querySelectorAll(".exp-card");

      expCards.forEach((card) => {
        const title = card.querySelector(".exp-card__title")?.textContent.toLowerCase() || "";
        const badge = card.querySelector(".exp-card__badge")?.textContent.toLowerCase() || "";
        const desc = card.querySelector(".exp-card__desc")?.textContent.toLowerCase() || "";

        if (query === "" || title.includes(query) || badge.includes(query) || desc.includes(query)) {
          card.style.display = "flex";
        } else {
          card.style.display = "none";
        }
      });
    });
  }

  // Open Add Experiment Modal
  if (addBtn && modal) {
    addBtn.addEventListener("click", () => {
      form.reset();
      if (coverPreview) coverPreview.hidden = true;
      if (subsContainer) subsContainer.innerHTML = "";
      openModal(modal);
    });
  }

  // Cover image preview
  if (coverInput && coverPreview) {
    coverInput.addEventListener("change", () => {
      const file = coverInput.files[0];
      if (file && file.type.startsWith("image/")) {
        const reader = new FileReader();
        reader.onload = (e) => {
          coverPreview.src = e.target.result;
          coverPreview.hidden = false;
        };
        reader.readAsDataURL(file);
      }
    });
  }

  // Add Sub-Experiment Builder
  if (addSubBtn && subsContainer) {
    addSubBtn.addEventListener("click", () => {
      const count = subsContainer.children.length;
      const letter = String.fromCharCode(65 + count); // A, B, C...

      const div = document.createElement("div");
      div.className = "sub-exp-block";
      div.style.padding = "12px";
      div.style.background = "var(--bg)";
      div.style.borderRadius = "8px";
      div.style.border = "1px solid var(--line)";
      div.style.marginTop = "8px";
      div.innerHTML = `
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
          <strong style="font-size:0.9rem; color:var(--accent-dark);">Sub-Experiment ${letter}</strong>
          <button type="button" class="btn btn--danger btn--sm" style="padding:2px 8px;" onclick="this.closest('.sub-exp-block').remove()">Remove</button>
        </div>
        <input type="hidden" name="sub_letter[]" value="${letter}">
        <div class="form-group" style="margin-bottom:8px;">
          <label style="font-size:0.8rem;">Sub-Experiment Title</label>
          <input type="text" name="sub_title[]" placeholder="e.g. Data Imputation" required style="padding:6px 10px; font-size:0.88rem;">
        </div>
        <div class="form-group">
          <label style="font-size:0.8rem;">Brief Description</label>
          <input type="text" name="sub_desc[]" placeholder="Brief outline of sub-task" style="padding:6px 10px; font-size:0.88rem;">
        </div>
      `;
      subsContainer.appendChild(div);
    });
  }

  // Handle Experiment Form Submit
  if (form) {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const submitBtn = form.querySelector('button[type="submit"]');
      submitBtn.disabled = true;
      submitBtn.textContent = "Saving...";

      try {
        const formData = new FormData(form);
        const res = await fetch("/api/experiments", {
          method: "POST",
          body: formData,
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.error || "Failed to create experiment.");
        }

        showToast("Experiment added successfully!");
        closeModal(modal);
        // Reload page to display fresh cards
        setTimeout(() => location.reload(), 400);
      } catch (err) {
        showToast(err.message, true);
        submitBtn.disabled = false;
        submitBtn.textContent = "Save Experiment";
      }
    });
  }

  // Delete Experiment with Confirmation
  document.querySelectorAll("[data-delete-exp]").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      e.stopPropagation();

      const expId = btn.getAttribute("data-delete-exp");
      const expTitle = btn.getAttribute("data-exp-title") || "this experiment";

      if (!confirm(`Are you sure you want to delete ${expTitle}? This action cannot be undone.`)) {
        return;
      }

      btn.disabled = true;
      try {
        const res = await fetch(`/api/experiments/${expId}`, {
          method: "DELETE",
        });

        if (!res.ok) throw new Error("Could not delete experiment.");

        showToast("Experiment deleted successfully.");
        const card = btn.closest(".exp-card");
        if (card) {
          card.style.transition = "opacity 0.25s ease, transform 0.25s ease";
          card.style.opacity = "0";
          card.style.transform = "scale(0.95)";
          setTimeout(() => card.remove(), 260);
        } else {
          location.reload();
        }
      } catch (err) {
        showToast(err.message, true);
        btn.disabled = false;
      }
    });
  });
}

/* --------------------------------------------------------------------------
   Modal Utilities
   -------------------------------------------------------------------------- */
function openModal(modal) {
  if (!modal) return;
  modal.classList.add("is-open");
  document.body.style.overflow = "hidden";
}

function closeModal(modal) {
  if (!modal) return;
  modal.classList.remove("is-open");
  document.body.style.overflow = "";
}

// Global modal close handlers
document.addEventListener("click", (e) => {
  if (e.target.matches(".modal-overlay") || e.target.closest("[data-close-modal]")) {
    const modal = e.target.closest(".modal-overlay");
    if (modal) closeModal(modal);
  }
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    document.querySelectorAll(".modal-overlay.is-open").forEach(closeModal);
  }
});

/* --------------------------------------------------------------------------
   Toast Notifications
   -------------------------------------------------------------------------- */
function initToasts() {
  // Global toast container
  let container = document.getElementById("toastContainer");
  if (!container) {
    container = document.createElement("div");
    container.id = "toastContainer";
    document.body.appendChild(container);
  }
}

function showToast(message, isError = false) {
  let container = document.getElementById("toastContainer");
  if (!container) {
    container = document.createElement("div");
    container.id = "toastContainer";
    document.body.appendChild(container);
  }

  const toast = document.createElement("div");
  toast.className = "toast-msg";
  if (isError) {
    toast.style.background = "var(--danger)";
  }

  toast.innerHTML = `
    <span style="font-weight:700;">${isError ? "✕" : "✓"}</span>
    <span>${message}</span>
  `;

  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s ease";
    setTimeout(() => toast.remove(), 320);
  }, 3500);
}
