"use strict";

/* 
   FELIX BUSINESS MANAGER
   Authentication, dashboard, clients, projects, interactions
*/

const TOKEN_KEY = "felix_business_manager_token";
const USER_KEY = "felix_business_manager_user";

function getStoredToken() {
    return (
        localStorage.getItem(TOKEN_KEY) ||
        sessionStorage.getItem(TOKEN_KEY)
    );
}

function getStoredUser() {
    const savedUser =
        localStorage.getItem(USER_KEY) ||
        sessionStorage.getItem(USER_KEY);

    if (!savedUser) return null;

    try {
        return JSON.parse(savedUser);
    } catch {
        return null;
    }
}

function saveSession(result) {
    const storage = result.user.is_guest
        ? localStorage
        : sessionStorage;

    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);

    storage.setItem(TOKEN_KEY, result.access_token);
    storage.setItem(USER_KEY, JSON.stringify(result.user));
}

function clearSession() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
}

const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

const state = {
    user: null,
    clients: [],
    projects: [],
    interactions: [],
    notificationTimer: null,
    pendingConfirmation: null
};

/* -------------------- API CLIENT -------------------- */

async function api(path, options = {}) {
    const token = getStoredToken();
    const headers = new Headers(options.headers || {});

    if (options.body && !(options.body instanceof FormData)) {
        headers.set("Content-Type", "application/json");
    }

    if (token) {
        headers.set("Authorization", `Bearer ${token}`);
    }

    let response;

    try {
        response = await fetch(path, {
            ...options,
            headers
        });
    } catch {
        throw new Error(
            "Unable to connect to the server. Check that your FastAPI application is running."
        );
    }

    if (response.status === 204) {
        return null;
    }

    const contentType = response.headers.get("content-type") || "";
    let result = null;

    if (contentType.includes("application/json")) {
        try {
            result = await response.json();
        } catch {
            result = null;
        }
    } else {
        const text = await response.text();
        result = text ? { detail: text } : null;
    }

    if (!response.ok) {
        if (response.status === 401 && token) {
            clearSession();
        }

        const detail = result?.detail || result?.message;

        let message = typeof detail === "string"
            ? detail
            : Array.isArray(detail)
                ? detail.map(item => item.msg || String(item)).join(" ")
                : `Request failed (${response.status}).`;

        if (response.status === 401) {
            message = "Your session may have expired, or your credentials are incorrect. Please sign in again.";
        } else if (response.status === 403) {
            message = "You do not have permission to perform this action.";
        } else if (response.status === 404 && !detail) {
            message = "The requested record or endpoint could not be found.";
        } else if (response.status === 422 && !detail) {
            message = "Some information is missing or invalid. Please review the form.";
        }

        const error = new Error(message);
        error.status = response.status;
        throw error;
    }

    return result;
}

/* -------------------- GENERAL UTILITIES -------------------- */

function escapeHTML(value) {
    return String(value ?? "").replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[character]);
}

function displayName(record) {
    return record?.full_name
        || record?.subject
        || record?.title
        || record?.name
        || record?.email
        || "Untitled";
}

function firstLetter(value) {
    return String(value || "F").trim().charAt(0).toUpperCase() || "F";
}

function formatDate(value, includeTime = false) {
    if (!value) return "No date set";

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return String(value);
    }

    const options = {
        day: "numeric",
        month: "short",
        year: "numeric"
    };

    if (includeTime) {
        options.hour = "2-digit";
        options.minute = "2-digit";
    }

    return new Intl.DateTimeFormat(undefined, options).format(date);
}

function normalizeList(data) {
    if (Array.isArray(data)) return data;
    if (Array.isArray(data?.items)) return data.items;
    if (Array.isArray(data?.results)) return data.results;
    if (Array.isArray(data?.data)) return data.data;
    return [];
}

function formatStatus(value) {
    const status = String(value || "planned").replace(/[_-]+/g, " ");
    return status.replace(/\b\w/g, character => character.toUpperCase());
}

function statusClass(value) {
    return String(value || "planned")
        .toLowerCase()
        .replace(/[^a-z0-9_-]/g, "-");
}

function showMessage(message, type = "success") {
    const box = $("#notification");
    if (!box) return;

    clearTimeout(state.notificationTimer);

    box.textContent = message;
    box.classList.toggle("error", type === "error");
    box.hidden = false;

    state.notificationTimer = setTimeout(() => {
        box.hidden = true;
    }, 4500);
}

function setAuthMessage(message = "", type = "error") {
    const box = $("#login-error");
    if (!box) return;

    box.textContent = message;
    box.hidden = !message;
    box.classList.toggle("success", type === "success");
}

function setButtonLoading(button, loading, loadingText, defaultText) {
    if (!button) return;

    button.disabled = loading;
    button.textContent = loading ? loadingText : defaultText;
}

function getErrorMessage(error) {
    return error?.message || "Something went wrong. Please try again.";
}

function getClientName(clientId) {
    const client = state.clients.find(
        item => String(item.id) === String(clientId)
    );

    return client ? displayName(client) : "Unknown client";
}

function getProjectName(projectId) {
    const project = state.projects.find(
        item => String(item.id) === String(projectId)
    );

    return project ? displayName(project) : "Unknown project";
}

function findRecord(records, id) {
    return records.find(record => String(record.id) === String(id));
}

/* -------------------- AUTHENTICATION SCREENS -------------------- */

const authForms = {
    login: $("#login-form"),
    register: $("#register-form"),
    forgot: $("#forgot-form"),
    reset: $("#reset-form")
};

function showAuthMode(mode, message = "", type = "error") {
    if (!Object.prototype.hasOwnProperty.call(authForms, mode)) {
        mode = "login";
    }

    $("#app-shell").hidden = true;
    $("#login-screen").hidden = false;

    Object.entries(authForms).forEach(([name, form]) => {
        if (form) form.hidden = name !== mode;
    });

    const headings = {
        login: "Welcome back",
        register: "Create your account",
        forgot: "Forgot your password?",
        reset: "Choose a new password"
    };

    const descriptions = {
        login: "Sign in to manage your clients, projects, and business activity.",
        register: "Create your account and start your own private business workspace.",
        forgot: "Enter your email address and we will send a reset link if your account exists.",
        reset: "Choose a strong new password to regain access to your workspace."
    };

    $("#login-heading").textContent = headings[mode];
    $("#login-description").textContent = descriptions[mode];

    const guestTrialAction = $("#guest-trial-action");

    if (guestTrialAction) {
        guestTrialAction.hidden = mode !== "login";
    }

    const switchArea = $("#auth-switch");
    switchArea.hidden = mode === "reset";

    if (mode === "login") {
        switchArea.innerHTML = `New to Felix Business Manager?
            <button class="text-button" type="button" data-auth-mode="register">Create an account</button>`;
    } else if (mode === "register") {
        switchArea.innerHTML = `Already have an account?
            <button class="text-button" type="button" data-auth-mode="login">Sign in</button>`;
    } else if (mode === "forgot") {
        switchArea.innerHTML = `Remembered your password?
            <button class="text-button" type="button" data-auth-mode="login">Return to sign in</button>`;
    }

    setAuthMessage(message, type);
}

function showLoginScreen(message = "", type = "error") {
    $("#app-shell").hidden = true;
    $("#login-screen").hidden = false;
    showAuthMode("login", message, type);
}

function saveAuthenticatedSession(result) {
    if (!result?.access_token || !result?.user) {
        throw new Error(
            "The server response is missing the access token or user details. Check your authentication response schema."
        );
    }

    saveSession(result);

    state.user = result.user;
    return result.user;
}

function showWorkspace(user) {
    state.user = user;

    const guestUpgradeBanner = $("#guest-upgrade-banner");

    if (guestUpgradeBanner) {
        guestUpgradeBanner.hidden = !user?.is_guest;
    }

    $("#login-screen").hidden = true;
    $("#app-shell").hidden = false;

    const fullName =
        user?.full_name || user?.name || user?.email || "Business Workspace";

    const firstName = fullName.trim().split(/\s+/)[0] || "there";

    $("#account-name").textContent = fullName;
    $("#greeting-name").textContent = firstName;

    $$(".profile-avatar").forEach(avatar => {
        avatar.textContent = firstLetter(fullName);
    });

    const heading = $("#view-dashboard .page-intro h1");

    if (heading) {
        heading.innerHTML =
            `Good to see you, <span id="greeting-name">${escapeHTML(firstName)}</span>.`;
    }
}

async function authenticateAndOpenWorkspace(result, message) {
    const user = saveAuthenticatedSession(result);

    showWorkspace(user);
    showMessage(message);

    await startApp();
}

/* -------------------- GUEST ACCESS -------------------- */

$("#guest-trial-button").addEventListener("click", async () => {
    const button = $("#guest-trial-button");

    setButtonLoading(
        button,
        true,
        "Starting your trial...",
        "Continue as Guest →"
    );

    setAuthMessage();

    try {
        const result = await api("/api/auth/guest", {
            method: "POST"
        });

        await authenticateAndOpenWorkspace(
            result,
            "Welcome! Your 48-hour free trial has started."
        );

    } catch (error) {
        setAuthMessage(getErrorMessage(error));

    } finally {
        setButtonLoading(
            button,
            false,
            "",
            "Continue as Guest →"
        );
    }
});

document.addEventListener("click", event => {
    const modeButton = event.target.closest("[data-auth-mode]");

    if (modeButton) {
        const mode = modeButton.dataset.authMode;

        showAuthMode(mode);

        if (mode === "register") $("#register-name").focus();

        if (mode === "forgot") {
            $("#forgot-email").value = $("#login-email").value.trim();
            $("#forgot-email").focus();
        }

        if (mode === "login") $("#login-email").focus();
        if (mode === "reset") $("#reset-password").focus();

        return;
    }

    const viewButton = event.target.closest("[data-view]");

    if (viewButton) {
        event.preventDefault();

        const view = viewButton.dataset.view;
        const focusTarget = viewButton.dataset.focus;

        goTo(view);

        if (focusTarget) {
            setTimeout(() => {
                const field = document.getElementById(focusTarget);
                if (field) field.focus({ preventScroll: true });
            }, 100);
        }
    }
});

/* -------------------- REGISTER -------------------- */

$("#register-form").addEventListener("submit", async event => {
    event.preventDefault();

    const button = $("#register-submit");
    const password = $("#register-password").value;

    if (password.length < 12) {
        setAuthMessage("Your password must contain at least 12 characters.");
        return;
    }

    setButtonLoading(button, true, "Creating account...", "Create account");
    setAuthMessage();

    try {
        const result = await api("/api/auth/register", {
            method: "POST",
            body: JSON.stringify({
                full_name: $("#register-name").value.trim(),
                email: $("#register-email").value.trim(),
                password
            })
        });

        await authenticateAndOpenWorkspace(
            result,
            `Welcome to Felix Business Manager, ${result.user.full_name || "there"}.`
        );

        $("#register-form").reset();
    } catch (error) {
        setAuthMessage(getErrorMessage(error));
    } finally {
        setButtonLoading(button, false, "", "Create account");
    }
});

/* -------------------- LOGIN -------------------- */

$("#login-form").addEventListener("submit", async event => {
    event.preventDefault();

    const button = $("#login-submit");

    setButtonLoading(button, true, "Signing in...", "Sign in");
    setAuthMessage();

    try {
        const result = await api("/api/auth/login", {
            method: "POST",
            body: JSON.stringify({
                email: $("#login-email").value.trim(),
                password: $("#login-password").value
            })
        });

        await authenticateAndOpenWorkspace(
            result,
            `Welcome back, ${result.user.full_name || "there"}.`
        );

        $("#login-password").value = "";
    } catch (error) {
        setAuthMessage(getErrorMessage(error));
    } finally {
        setButtonLoading(button, false, "", "Sign in");
    }
});

/* -------------------- PASSWORD RECOVERY -------------------- */

$("#forgot-form").addEventListener("submit", async event => {
    event.preventDefault();

    const button = $("#forgot-submit");

    setButtonLoading(button, true, "Sending link...", "Send reset link");
    setAuthMessage();

    try {
        const result = await api("/api/auth/forgot-password", {
            method: "POST",
            body: JSON.stringify({
                email: $("#forgot-email").value.trim()
            })
        });

        showAuthMode(
            "forgot",
            result?.message ||
                "If an account exists for that email, a password-reset link will be sent.",
            "success"
        );
    } catch (error) {
        setAuthMessage(getErrorMessage(error));
    } finally {
        setButtonLoading(button, false, "", "Send reset link");
    }
});

$("#reset-form").addEventListener("submit", async event => {
    event.preventDefault();

    const button = $("#reset-submit");
    const password = $("#reset-password").value;
    const confirmation = $("#reset-password-confirm").value;

    if (password.length < 12) {
        setAuthMessage("Your new password must contain at least 12 characters.");
        return;
    }

    if (password !== confirmation) {
        setAuthMessage("The two passwords do not match.");
        return;
    }

    const resetToken =
        new URLSearchParams(window.location.search).get("reset_token");

    if (!resetToken) {
        setAuthMessage(
            "The reset token is missing. Please request a new password-reset link."
        );
        return;
    }

    setButtonLoading(button, true, "Resetting password...", "Reset password");
    setAuthMessage();

    try {
        const result = await api("/api/auth/reset-password", {
            method: "POST",
            body: JSON.stringify({
                token: resetToken,
                new_password: password
            })
        });

        clearSession();

        window.history.replaceState(
            {},
            document.title,
            window.location.pathname
        );

        $("#login-form").reset();
        $("#reset-form").reset();

        showAuthMode(
            "login",
            result?.message ||
                "Your password has been reset. Please sign in with your new password.",
            "success"
        );
    } catch (error) {
        setAuthMessage(getErrorMessage(error));
    } finally {
        setButtonLoading(button, false, "", "Reset password");
    }
});

/* -------------------- NAVIGATION -------------------- */

const viewNames = {
    dashboard: "Dashboard",
    clients: "Clients",
    projects: "Projects",
    interactions: "Interactions"
};

function goTo(view) {
    if (!Object.prototype.hasOwnProperty.call(viewNames, view)) {
        view = "dashboard";
    }

    Object.keys(viewNames).forEach(name => {
        const section = $(`#view-${name}`);
        if (section) section.hidden = name !== view;
    });

    $$(".nav-item").forEach(button => {
        const active = button.dataset.view === view;
        button.classList.toggle("active", active);

        if (active) {
            button.setAttribute("aria-current", "page");
        } else {
            button.removeAttribute("aria-current");
        }
    });

    $("#page-breadcrumb").textContent = viewNames[view];
    $("#app-shell").classList.remove("sidebar-open");

    if (view === "clients") loadClients().catch(handleError);
    if (view === "projects") loadProjects().catch(handleError);
    if (view === "interactions") loadInteractions().catch(handleError);
}

/* Mobile navigation */

$("#menu-button").addEventListener("click", () => {
    $("#app-shell").classList.toggle("sidebar-open");
});

$("#sidebar-backdrop").addEventListener("click", () => {
    $("#app-shell").classList.remove("sidebar-open");
});

/* -------------------- REFERENCE DATA -------------------- */

async function refreshReferenceData() {
    const [clientsResult, projectsResult] = await Promise.all([
        api("/api/clients"),
        api("/api/projects")
    ]);

    state.clients = normalizeList(clientsResult);
    state.projects = normalizeList(projectsResult);

    populateSelect($("#project-client"), state.clients, "Select a client");
    populateSelect($("#interaction-client"), state.clients, "Select a client");

    filterInteractionProjects();

    $("#nav-client-count").textContent = state.clients.length;
    $("#nav-project-count").textContent = state.projects.length;
}

function populateSelect(select, records, placeholder) {
    if (!select) return;

    const previousValue = select.value;
    const isProjectSelect = select.id === "interaction-project";

    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = isProjectSelect
        ? "No project linked"
        : placeholder;

    select.replaceChildren(defaultOption);

    records.forEach(record => {
        const option = document.createElement("option");
        option.value = record.id;
        option.textContent = displayName(record);
        select.appendChild(option);
    });

    if ([...select.options].some(option => option.value === previousValue)) {
        select.value = previousValue;
    }
}

function filterInteractionProjects() {
    const clientSelect = $("#interaction-client");
    const projectSelect = $("#interaction-project");

    if (!clientSelect || !projectSelect) return;

    const clientId = clientSelect.value;

    const filtered = clientId
        ? state.projects.filter(
            project => String(project.client_id) === String(clientId)
        )
        : state.projects;

    populateSelect(projectSelect, filtered, "No project linked");
}

/* -------------------- DASHBOARD -------------------- */

async function loadDashboard() {
    const result = await api("/api/dashboard");

    const clients = Number(
        result?.total_clients ??
        result?.clients_count ??
        state.clients.length
    );

    const projects = Number(
        result?.total_projects ??
        result?.projects_count ??
        state.projects.length
    );

    const active = Number(
        result?.active_projects ??
        result?.active_projects_count ??
        state.projects.filter(project =>
            ["active", "in_progress", "in-progress"].includes(
                String(project.status || "").toLowerCase()
            )
        ).length
    );

    const interactions = Number(
        result?.total_interactions ??
        result?.interactions_count ??
        state.interactions.length
    );

    $("#stat-clients").textContent = clients;
    $("#stat-projects").textContent = projects;
    $("#stat-active").textContent = active;
    $("#stat-interactions").textContent = interactions;

    $("#nav-client-count").textContent = state.clients.length;
    $("#nav-project-count").textContent = state.projects.length;

    const recent = normalizeList(
        result?.recent_interactions ??
        result?.recent_activity ??
        result?.interactions ??
        state.interactions
    );

    renderRecentInteractions(recent.slice(0, 6));
}

function renderRecentInteractions(records) {
    const container = $("#recent-interactions");

    if (!container) return;

    if (!records.length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">↗</div>
                <strong>Your next conversation starts here.</strong>
                <p>Interactions you record will appear in this timeline.</p>
                <button class="secondary-button" type="button" data-view="interactions">Record an interaction</button>
            </div>`;
        return;
    }

    container.innerHTML = records.map(record => {
        const title = displayName(record);
        const clientName =
            record.client?.full_name ||
            record.client?.name ||
            record.client_name ||
            getClientName(record.client_id);

        const date =
            record.occurred_at ||
            record.interaction_date ||
            record.created_at ||
            record.date;

        const type =
            record.interaction_type ||
            record.type ||
            "Activity";

        const details = record.details || record.notes || "";

        return `
            <article class="activity-item">
                <div class="activity-marker">↗</div>
                <div class="activity-copy">
                    <strong>${escapeHTML(title)}</strong>
                    <p>${escapeHTML(clientName)}${details ? ` · ${escapeHTML(details)}` : ""}</p>
                    <small>${escapeHTML(formatDate(date, true))}</small>
                </div>
                <span class="activity-type">${escapeHTML(formatStatus(type))}</span>
            </article>`;
    }).join("");
}

/* -------------------- CLIENTS -------------------- */

async function loadClients() {
    const container = $("#clients-list");

    try {
        const result = await api("/api/clients");
        state.clients = normalizeList(result);

        $("#nav-client-count").textContent = state.clients.length;
        $("#clients-summary").textContent =
            `${state.clients.length} client${state.clients.length === 1 ? "" : "s"} in your workspace`;

        populateSelect($("#project-client"), state.clients, "Select a client");
        populateSelect($("#interaction-client"), state.clients, "Select a client");
        filterInteractionProjects();

        renderClients();
    } catch (error) {
        container.innerHTML =
            `<div class="error-state">${escapeHTML(getErrorMessage(error))}</div>`;
        throw error;
    }
}

function renderClients() {
    const container = $("#clients-list");
    const search = ($("#client-search").value || "").trim().toLowerCase();

    const records = state.clients.filter(client => {
        const searchable = [
            client.full_name,
            client.email,
            client.phone,
            client.company,
            client.notes
        ].join(" ").toLowerCase();

        return searchable.includes(search);
    });

    if (!records.length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">♙</div>
                <strong>${search ? "No matching clients" : "Your client directory is ready."}</strong>
                <p>${search ? "Try a different search term." : "Add your first client using the form above."}</p>
            </div>`;
        return;
    }

    container.innerHTML = records.map(client => `
        <article class="record-card">
            <div class="record-avatar">${escapeHTML(firstLetter(displayName(client)))}</div>
            <div class="record-main">
                <div class="record-title-row">
                    <strong class="record-title">${escapeHTML(displayName(client))}</strong>
                </div>
                ${client.company ? `<div class="record-email">${escapeHTML(client.company)}</div>` : ""}
                <div class="record-meta">
                    ${client.email ? `<span>✉ ${escapeHTML(client.email)}</span>` : ""}
                    ${client.phone ? `<span>☎ ${escapeHTML(client.phone)}</span>` : ""}
                </div>
                ${client.notes ? `<p class="record-description">${escapeHTML(client.notes)}</p>` : ""}
            </div>
            <div class="record-actions">
                <button class="small-action" type="button" data-action="edit-client" data-id="${escapeHTML(client.id)}" aria-label="Edit client" title="Edit">✎</button>
                <button class="small-action delete" type="button" data-action="delete-client" data-id="${escapeHTML(client.id)}" aria-label="Delete client" title="Delete">×</button>
            </div>
        </article>
    `).join("");
}

function resetClientForm() {
    $("#client-form").reset();
    $("#client-id").value = "";
    $("#client-form-heading").textContent = "Add a client";
    $("#client-submit").innerHTML = 'Save client <span>→</span>';
    $("#client-cancel").hidden = true;
}

$("#client-form").addEventListener("submit", async event => {
    event.preventDefault();

    const id = $("#client-id").value;
    const button = $("#client-submit");

    const payload = {
        full_name: $("#client-name").value.trim(),
        email: $("#client-email").value.trim() || null,
        phone: $("#client-phone").value.trim() || null,
        company: $("#client-company").value.trim() || null,
        notes: $("#client-notes").value.trim() || null
    };

    setButtonLoading(
        button,
        true,
        "Saving...",
        id ? "Update client" : "Save client"
    );

    try {
        await api(
            id ? `/api/clients/${encodeURIComponent(id)}` : "/api/clients",
            {
                method: id ? "PATCH" : "POST",
                body: JSON.stringify(payload)
            }
        );

        resetClientForm();
        await refreshReferenceData();

        await Promise.all([
            loadClients(),
            loadProjects(),
            loadDashboard()
        ]);

        showMessage(
            id ? "Client updated successfully." : "Client added successfully."
        );
    } catch (error) {
        showMessage(getErrorMessage(error), "error");
    } finally {
        button.disabled = false;
        button.innerHTML = id
            ? "Update client <span>→</span>"
            : 'Save client <span>→</span>';
    }
});

function editClient(id) {
    const client = findRecord(state.clients, id);
    if (!client) return;

    $("#client-id").value = client.id;
    $("#client-name").value = client.full_name || "";
    $("#client-email").value = client.email || "";
    $("#client-phone").value = client.phone || "";
    $("#client-company").value = client.company || "";
    $("#client-notes").value = client.notes || "";

    $("#client-form-heading").textContent = "Edit client";
    $("#client-submit").innerHTML = 'Update client <span>→</span>';
    $("#client-cancel").hidden = false;

    $("#client-form").scrollIntoView({
        behavior: "smooth",
        block: "start"
    });

    $("#client-name").focus({ preventScroll: true });
}

$("#client-cancel").addEventListener("click", resetClientForm);
$("#client-search").addEventListener("input", renderClients);

/* -------------------- PROJECTS -------------------- */

async function loadProjects() {
    const container = $("#projects-list");

    try {
        const result = await api("/api/projects");
        state.projects = normalizeList(result);

        $("#nav-project-count").textContent = state.projects.length;
        $("#projects-summary").textContent =
            `${state.projects.length} project${state.projects.length === 1 ? "" : "s"} in your portfolio`;

        populateSelect($("#project-client"), state.clients, "Select a client");
        filterInteractionProjects();

        renderProjects();
    } catch (error) {
        container.innerHTML =
            `<div class="error-state">${escapeHTML(getErrorMessage(error))}</div>`;
        throw error;
    }
}

function renderProjects() {
    const container = $("#projects-list");
    const search = ($("#project-search").value || "").trim().toLowerCase();

    const records = state.projects.filter(project => {
        const searchable = [
            project.title,
            project.description,
            project.status,
            getClientName(project.client_id)
        ].join(" ").toLowerCase();

        return searchable.includes(search);
    });

    if (!records.length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">▤</div>
                <strong>${search ? "No matching projects" : "Give your next idea a home."}</strong>
                <p>${search ? "Try a different search term." : "Create a project using the form above."}</p>
            </div>`;
        return;
    }

    container.innerHTML = records.map(project => {
        const status = project.status || "planned";
        const deadline = project.due_date;

        return `
            <article class="record-card">
                <div class="record-avatar project-avatar">▤</div>
                <div class="record-main">
                    <div class="record-title-row">
                        <strong class="record-title">${escapeHTML(displayName(project))}</strong>
                        <span class="status-pill status-${escapeHTML(statusClass(status))}">${escapeHTML(formatStatus(status))}</span>
                    </div>
                    <div class="record-meta">
                        <span>Client: ${escapeHTML(getClientName(project.client_id))}</span>
                        ${deadline ? `<span>Deadline: ${escapeHTML(formatDate(deadline))}</span>` : ""}
                        ${project.budget != null ? `<span>Budget: ${escapeHTML(String(project.budget))}</span>` : ""}
                    </div>
                    ${project.description ? `<p class="record-description">${escapeHTML(project.description)}</p>` : ""}
                </div>
                <div class="record-actions">
                    <button class="small-action" type="button" data-action="edit-project" data-id="${escapeHTML(project.id)}" aria-label="Edit project" title="Edit">✎</button>
                    <button class="small-action delete" type="button" data-action="delete-project" data-id="${escapeHTML(project.id)}" aria-label="Delete project" title="Delete">×</button>
                </div>
            </article>`;
    }).join("");
}

function resetProjectForm() {
    $("#project-form").reset();
    $("#project-id").value = "";
    $("#project-form-heading").textContent = "Create a project";
    $("#project-submit").innerHTML = 'Save project <span>→</span>';
    $("#project-cancel").hidden = true;
}

$("#project-form").addEventListener("submit", async event => {
    event.preventDefault();

    const id = $("#project-id").value;
    const button = $("#project-submit");
    const dueDate = $("#project-deadline").value;

    const payload = {
        title: $("#project-name").value.trim(),
        client_id: Number($("#project-client").value),
        status: $("#project-status").value,
        due_date: dueDate || null,
        description: $("#project-description").value.trim() || null
    };

    setButtonLoading(
        button,
        true,
        "Saving...",
        id ? "Update project" : "Save project"
    );

    try {
        await api(
            id ? `/api/projects/${encodeURIComponent(id)}` : "/api/projects",
            {
                method: id ? "PATCH" : "POST",
                body: JSON.stringify(payload)
            }
        );

        resetProjectForm();
        await refreshReferenceData();

        await Promise.all([
            loadProjects(),
            loadClients(),
            loadInteractions(),
            loadDashboard()
        ]);

        showMessage(
            id ? "Project updated successfully." : "Project created successfully."
        );
    } catch (error) {
        showMessage(getErrorMessage(error), "error");
    } finally {
        button.disabled = false;
        button.innerHTML = id
            ? "Update project <span>→</span>"
            : 'Save project <span>→</span>';
    }
});

function editProject(id) {
    const project = findRecord(state.projects, id);
    if (!project) return;

    $("#project-id").value = project.id;
    $("#project-name").value = project.title || "";
    $("#project-client").value = project.client_id ?? "";
    $("#project-status").value = project.status || "planned";
    $("#project-deadline").value = project.due_date || "";
    $("#project-description").value = project.description || "";

    $("#project-form-heading").textContent = "Edit project";
    $("#project-submit").innerHTML = 'Update project <span>→</span>';
    $("#project-cancel").hidden = false;

    $("#project-form").scrollIntoView({
        behavior: "smooth",
        block: "start"
    });

    $("#project-name").focus({ preventScroll: true });
}

$("#project-cancel").addEventListener("click", resetProjectForm);
$("#project-search").addEventListener("input", renderProjects);

/* -------------------- INTERACTIONS -------------------- */

async function loadInteractions() {
    const container = $("#interactions-list");

    try {
        const result = await api("/api/interactions");
        state.interactions = normalizeList(result);

        $("#interactions-summary").textContent =
            `${state.interactions.length} interaction${state.interactions.length === 1 ? "" : "s"} recorded`;

        renderInteractions();
    } catch (error) {
        container.innerHTML =
            `<div class="error-state">${escapeHTML(getErrorMessage(error))}</div>`;
        throw error;
    }
}

function renderInteractions() {
    const container = $("#interactions-list");
    const search = ($("#interaction-search").value || "").trim().toLowerCase();

    const records = [...state.interactions]
        .sort((a, b) =>
            new Date(b.occurred_at || b.created_at || 0) -
            new Date(a.occurred_at || a.created_at || 0)
        )
        .filter(interaction => {
            const searchable = [
                interaction.subject,
                interaction.details,
                interaction.interaction_type,
                getClientName(interaction.client_id),
                getProjectName(interaction.project_id)
            ].join(" ").toLowerCase();

            return searchable.includes(search);
        });

    if (!records.length) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">↗</div>
                <strong>${search ? "No matching interactions" : "Make the details count."}</strong>
                <p>${search ? "Try a different search term." : "Record your first call, meeting, email, or business update."}</p>
            </div>`;
        return;
    }

    container.innerHTML = records.map(interaction => {
        const title = displayName(interaction);
        const type = interaction.interaction_type || "note";
        const date = interaction.occurred_at || interaction.created_at;
        const details = interaction.details || "";

        return `
            <article class="record-card">
                <div class="record-avatar interaction-avatar">↗</div>
                <div class="record-main">
                    <div class="record-title-row">
                        <strong class="record-title">${escapeHTML(title)}</strong>
                        <span class="status-pill">${escapeHTML(formatStatus(type))}</span>
                    </div>
                    <div class="record-meta">
                        <span>Client: ${escapeHTML(getClientName(interaction.client_id))}</span>
                        ${interaction.project_id ? `<span>Project: ${escapeHTML(getProjectName(interaction.project_id))}</span>` : ""}
                        <span>${escapeHTML(formatDate(date, true))}</span>
                    </div>
                    ${details ? `<p class="record-description">${escapeHTML(details)}</p>` : ""}
                </div>
                <div class="record-actions">
                    <button class="small-action" type="button" data-action="edit-interaction" data-id="${escapeHTML(interaction.id)}" aria-label="Edit interaction" title="Edit">✎</button>
                    <button class="small-action delete" type="button" data-action="delete-interaction" data-id="${escapeHTML(interaction.id)}" aria-label="Delete interaction" title="Delete">×</button>
                </div>
            </article>`;
    }).join("");
}

function resetInteractionForm() {
    $("#interaction-form").reset();
    $("#interaction-id").value = "";
    $("#interaction-form-heading").textContent = "Record an interaction";
    $("#interaction-submit").innerHTML = 'Save interaction <span>→</span>';
    $("#interaction-cancel").hidden = true;

    const date = new Date();
    date.setMinutes(date.getMinutes() - date.getTimezoneOffset());

    $("#interaction-date").value = date.toISOString().slice(0, 16);

    filterInteractionProjects();
}

$("#interaction-client").addEventListener("change", filterInteractionProjects);

$("#interaction-form").addEventListener("submit", async event => {
    event.preventDefault();

    const id = $("#interaction-id").value;
    const button = $("#interaction-submit");
    const selectedDate = $("#interaction-date").value;

    const payload = {
        subject: $("#interaction-title").value.trim(),
        client_id: Number($("#interaction-client").value),
        project_id: $("#interaction-project").value
            ? Number($("#interaction-project").value)
            : null,
        interaction_type: $("#interaction-type").value,
        occurred_at: selectedDate
            ? new Date(selectedDate).toISOString()
            : null,
        details: $("#interaction-notes").value.trim() || null
    };

    setButtonLoading(
        button,
        true,
        "Saving...",
        id ? "Update interaction" : "Save interaction"
    );

    try {
        await api(
            id
                ? `/api/interactions/${encodeURIComponent(id)}`
                : "/api/interactions",
            {
                method: id ? "PATCH" : "POST",
                body: JSON.stringify(payload)
            }
        );

        resetInteractionForm();
        await refreshReferenceData();

        await Promise.all([
            loadInteractions(),
            loadDashboard()
        ]);

        showMessage(
            id
                ? "Interaction updated successfully."
                : "Interaction recorded successfully."
        );
    } catch (error) {
        showMessage(getErrorMessage(error), "error");
    } finally {
        button.disabled = false;
        button.innerHTML = id
            ? "Update interaction <span>→</span>"
            : 'Save interaction <span>→</span>';
    }
});

function editInteraction(id) {
    const interaction = findRecord(state.interactions, id);
    if (!interaction) return;

    $("#interaction-id").value = interaction.id;
    $("#interaction-title").value = interaction.subject || "";
    $("#interaction-client").value = interaction.client_id ?? "";

    filterInteractionProjects();

    $("#interaction-project").value = interaction.project_id ?? "";
    $("#interaction-type").value = interaction.interaction_type || "note";

    const dateValue = interaction.occurred_at || "";

    if (dateValue) {
        const date = new Date(dateValue);
        date.setMinutes(date.getMinutes() - date.getTimezoneOffset());

        $("#interaction-date").value = date.toISOString().slice(0, 16);
    } else {
        $("#interaction-date").value = "";
    }

    $("#interaction-notes").value = interaction.details || "";
    $("#interaction-form-heading").textContent = "Edit interaction";
    $("#interaction-submit").innerHTML = 'Update interaction <span>→</span>';
    $("#interaction-cancel").hidden = false;

    $("#interaction-form").scrollIntoView({
        behavior: "smooth",
        block: "start"
    });

    $("#interaction-title").focus({ preventScroll: true });
}

$("#interaction-cancel").addEventListener("click", resetInteractionForm);
$("#interaction-search").addEventListener("input", renderInteractions);

/* -------------------- EDIT / DELETE ACTIONS -------------------- */

document.addEventListener("click", event => {
    const button = event.target.closest("[data-action]");
    if (!button) return;

    const { action, id } = button.dataset;

    if (action === "edit-client") editClient(id);
    if (action === "edit-project") editProject(id);
    if (action === "edit-interaction") editInteraction(id);

    if (action === "delete-client") {
        askForConfirmation(
            "Delete this client?",
            "Only proceed if you are sure. Your backend may prevent deleting a client linked to projects or interactions.",
            () => deleteRecord("clients", id, "Client deleted.")
        );
    }

    if (action === "delete-project") {
        askForConfirmation(
            "Delete this project?",
            "This will remove the project record. Any linked interactions may prevent deletion.",
            () => deleteRecord("projects", id, "Project deleted.")
        );
    }

    if (action === "delete-interaction") {
        askForConfirmation(
            "Delete this interaction?",
            "This interaction record will be permanently deleted.",
            () => deleteRecord("interactions", id, "Interaction deleted.")
        );
    }
});

function askForConfirmation(title, description, callback) {
    const dialog = $("#confirm-dialog");

    $("#confirm-title").textContent = title;
    $("#confirm-description").textContent = description;

    state.pendingConfirmation = callback;

    if (typeof dialog.showModal === "function") {
        dialog.showModal();
    } else if (window.confirm(`${title}\n\n${description}`)) {
        const action = state.pendingConfirmation;
        state.pendingConfirmation = null;
        if (action) action();
    }
}

$("#confirm-cancel").addEventListener("click", () => {
    state.pendingConfirmation = null;
    $("#confirm-dialog").close();
});

$("#confirm-accept").addEventListener("click", async () => {
    const action = state.pendingConfirmation;
    state.pendingConfirmation = null;
    $("#confirm-dialog").close();

    if (action) await action();
});

async function deleteRecord(resource, id, successMessage) {
    try {
        await api(`/api/${resource}/${encodeURIComponent(id)}`, {
            method: "DELETE"
        });

        if (resource === "clients") resetClientForm();
        if (resource === "projects") resetProjectForm();
        if (resource === "interactions") resetInteractionForm();

        await refreshReferenceData();

        await Promise.all([
            loadClients(),
            loadProjects(),
            loadInteractions(),
            loadDashboard()
        ]);

        showMessage(successMessage);
    } catch (error) {
        showMessage(getErrorMessage(error), "error");
    }
}

/* -------------------- ERROR HANDLING -------------------- */

function handleError(error) {
    console.error("Felix Business Manager:", error);

    if (!getStoredToken()) {
        showLoginScreen("Please sign in to continue.");
        return;
    }

    showMessage(getErrorMessage(error), "error");
}

/* -------------------- LOGOUT -------------------- */

$("#logout-button").addEventListener("click", () => {
    clearSession();

    state.user = null;
    state.clients = [];
    state.projects = [];
    state.interactions = [];

    $("#login-form").reset();
    $("#register-form").reset();
    $("#forgot-form").reset();
    $("#reset-form").reset();

    showLoginScreen("You have signed out successfully.", "success");
});

/* -------------------- APPLICATION STARTUP -------------------- */

async function startApp() {
    try {
        await refreshReferenceData();

        const interactionsResult = await api("/api/interactions");
        state.interactions = normalizeList(interactionsResult);

        await Promise.all([
            loadDashboard(),
            loadClients(),
            loadProjects(),
            loadInteractions()
        ]);
    } catch (error) {
        handleError(error);
    }
}

async function initializeAuthentication() {
    $("#auth-year").textContent = new Date().getFullYear();

    $("#today-label").textContent = new Intl.DateTimeFormat(undefined, {
        weekday: "short",
        day: "numeric",
        month: "short",
        year: "numeric"
    }).format(new Date());

    const params = new URLSearchParams(window.location.search);
    const resetToken = params.get("reset_token");

    if (resetToken) {
        showAuthMode("reset");
        return;
    }

    const token = getStoredToken();

    if (!token) {
        showLoginScreen();
        return;
    }

    try {
    const user = await api("/api/auth/me");

    saveSession({
        access_token: token,
        user: user
    });

    showWorkspace(user);

    await startApp();

    } catch (error) {

        if (error.status === 401) {
            clearSession();

            showLoginScreen(
                "Your session has expired. Please sign in again."
            );

            return;
        }

        showLoginScreen(
            "Unable to verify your session. Check your internet connection and refresh the page. Your saved session has been preserved."
        );
    }
}

/* 
   INTERACTIVE WORKSPACE CONTROLS
*/

(() => {
    const getElement = id => document.getElementById(id);

    const profileButton = getElement("profile-button");
    const profileMenu = getElement("profile-menu");
    const profileEmail = getElement("profile-email");

    function getCurrentUser() {
        return getStoredUser();
    }

    function navigateTo(view) {
        if (typeof goTo === "function") {
            goTo(view);
        } else {
            console.error(`Navigation to "${view}" failed: goTo() is unavailable.`);
        }
    }

    getElement("workspace-home-button")?.addEventListener("click", () => {
        navigateTo("dashboard");
    });

    getElement("motivation-button")?.addEventListener("click", () => {
        navigateTo("interactions");
    });

    getElement("profile-dashboard-button")?.addEventListener("click", () => {
        closeProfileMenu();
        navigateTo("dashboard");
    });

    function openProfileMenu() {
        if (!profileButton || !profileMenu) return;

        profileMenu.hidden = false;
        profileButton.setAttribute("aria-expanded", "true");

        const user = getCurrentUser();

        if (profileEmail) {
            profileEmail.textContent =
                user?.email || "Signed-in personal workspace";
        }
    }

    function closeProfileMenu() {
        if (!profileButton || !profileMenu) return;

        profileMenu.hidden = true;
        profileButton.setAttribute("aria-expanded", "false");
    }

    profileButton?.addEventListener("click", () => {
        const isOpen =
            profileButton.getAttribute("aria-expanded") === "true";

        if (isOpen) {
            closeProfileMenu();
        } else {
            openProfileMenu();
        }
    });

    document.addEventListener("click", event => {
        if (!profileButton || !profileMenu) return;

        const clickedInside =
            profileButton.contains(event.target) ||
            profileMenu.contains(event.target);

        if (!clickedInside) {
            closeProfileMenu();
        }
    });

    document.addEventListener("keydown", event => {
        if (event.key === "Escape") {
            closeProfileMenu();
        }
    });

    getElement("profile-logout-button")?.addEventListener("click", () => {
        const existingLogoutButton = getElement("logout-button");

        closeProfileMenu();

        if (existingLogoutButton) {
            existingLogoutButton.click();
            return;
        }

        clearSession();

        window.location.assign("/");

    });

    function updateProfileName() {
        const user = getCurrentUser();
        const accountName = getElement("account-name");
        const avatars = document.querySelectorAll(".profile-avatar");

        const name =
            user?.full_name ||
            user?.name ||
            user?.username ||
            "Felix Ogunbowale";

        if (accountName) {
            accountName.textContent = name;
        }

        avatars.forEach(avatar => {
            avatar.textContent = firstLetter(name);
        });
    }

    updateProfileName();

    getElement("brand-home-link")?.addEventListener("click", event => {
        event.preventDefault();

        const token = getStoredToken();        
        const appShell = getElement("app-shell");
        const loginScreen = getElement("login-screen");

        if (token && appShell && !appShell.hidden) {
            navigateTo("dashboard");
            return;
        }

        if (typeof showAuthMode === "function") {
            showAuthMode("login");
        } else if (loginScreen) {
            loginScreen.hidden = false;
        } else {
            window.location.assign("/");
        }
    });
})();

/* -------------------- DEFAULT INTERACTION DATE -------------------- */

const initialInteractionDate = new Date();

initialInteractionDate.setMinutes(
    initialInteractionDate.getMinutes() -
    initialInteractionDate.getTimezoneOffset()
);

$("#interaction-date").value =
    initialInteractionDate.toISOString().slice(0, 16);


/* -------------------- PASSWORD VISIBILITY TOGGLE -------------------- */

document.addEventListener("click", event => {
    const toggleButton = event.target.closest("[data-password-toggle]");

    if (!toggleButton) return;

    const inputId = toggleButton.dataset.passwordToggle;
    const passwordInput = document.getElementById(inputId);

    if (!passwordInput) return;

    const isPasswordHidden = passwordInput.type === "password";

    passwordInput.type = isPasswordHidden ? "text" : "password";

    toggleButton.setAttribute(
        "aria-label",
        isPasswordHidden ? "Hide password" : "Show password"
    );

    toggleButton.setAttribute(
        "aria-pressed",
        String(isPasswordHidden)
    );
});

/* -------------------- START APPLICATION -------------------- */

initializeAuthentication();
