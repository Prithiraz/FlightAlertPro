/**
 * FlightAlertPro — Extension Popup
 *
 * Handles user authentication against the FlightAlertPro backend.
 * On success the JWT and email are persisted in chrome.storage.local
 * so the background service worker can use them when creating alerts.
 */

"use strict";

const API_BASE_URL = "https://flightalertpro.com";

/* ── DOM references ────────────────────────────────────────── */
const loginView = document.getElementById("login-view");
const loggedInView = document.getElementById("logged-in-view");
const emailInput = document.getElementById("email");
const passwordInput = document.getElementById("password");
const loginBtn = document.getElementById("login-btn");
const logoutBtn = document.getElementById("logout-btn");
const statusMsg = document.getElementById("status-msg");
const displayEmail = document.getElementById("display-email");

/* ── Helpers ───────────────────────────────────────────────── */

function setStatus(message, type = "") {
  statusMsg.textContent = message;
  statusMsg.className = type; // "success" | "error" | ""
}

function showLoggedIn(email) {
  loginView.style.display = "none";
  loggedInView.style.display = "block";
  displayEmail.textContent = email;
}

function showLogin() {
  loginView.style.display = "block";
  loggedInView.style.display = "none";
  statusMsg.textContent = "";
}

/* ── Check existing session on popup open ──────────────────── */
chrome.storage.local.get(["fap_token", "fap_email"], (stored) => {
  if (stored.fap_token && stored.fap_email) {
    showLoggedIn(stored.fap_email);
  } else {
    showLogin();
  }
});

/* ── Login ─────────────────────────────────────────────────── */
loginBtn.addEventListener("click", async () => {
  const email = emailInput.value.trim();
  const password = passwordInput.value;

  if (!email || !password) {
    setStatus("Please enter your email and password.", "error");
    return;
  }

  loginBtn.disabled = true;
  loginBtn.textContent = "Signing in…";
  setStatus("", "");

  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    let data = null;
    try {
      data = await response.json();
    } catch (_) {
      if (!response.ok) {
        throw new Error(`Server error ${response.status} (invalid response format)`);
      }
      // Response is OK but not JSON — proceed with null data (token check below will catch it).
    }

    if (!response.ok) {
      const errDetail = data && (data.detail || data.message);
      throw new Error(errDetail || `Error ${response.status}`);
    }

    // The backend is expected to return { token: "...", email: "..." }
    // Adjust the field names below if the actual shape differs.
    const token =
      data &&
      (data.token || data.access_token || (data.session && data.session.access_token));

    if (!token) {
      throw new Error("No token returned by the server.");
    }

    // Persist credentials securely in extension storage.
    chrome.storage.local.set({ fap_token: token, fap_email: email }, () => {
      showLoggedIn(email);
      setStatus("Signed in successfully!", "success");
    });
  } catch (err) {
    setStatus(err.message || "Sign-in failed. Please try again.", "error");
    loginBtn.disabled = false;
    loginBtn.textContent = "Sign In";
  }
});

/* Allow pressing Enter in the password field to submit */
passwordInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") loginBtn.click();
});

/* ── Logout ────────────────────────────────────────────────── */
logoutBtn.addEventListener("click", () => {
  chrome.storage.local.remove(["fap_token", "fap_email"], () => {
    showLogin();
    emailInput.value = "";
    passwordInput.value = "";
  });
});
